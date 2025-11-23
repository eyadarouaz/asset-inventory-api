import os
import traceback
import logging
import json
import time
from datetime import datetime

from celery import shared_task
from jinja2 import Template
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from app.deployment_service import DeploymentService, DeploymentValidationError, TerraformExecutionError
from app.minio_client import upload_to_minio
from app.models import DeploymentJob

logger = logging.getLogger(__name__)
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'

@shared_task(bind=True, max_retries=0)
def deploy_vm_via_terraform(self, job_id: int):
    try:
        job = DeploymentJob.objects.get(id=job_id)

        if DEMO_MODE:
            return deploy_vm_demo_mode(job)
        
        service = DeploymentService()
        
        logger.info(f"Starting deployment workflow for job {job_id}: {job.name}")
        
        is_valid, errors = service.validate_deployment(job)
        if not is_valid:
            job.status = 'validation_failed'
            job.plan_output = f"Validation errors: {errors}"
            job.save()
            return {
                'success': False,
                'job_id': job_id,
                'error': 'Validation failed',
                'details': errors
            }
        
        if not job.minio_object:
            logger.info(f"Generating plan for job {job_id}")
            plan_result = service.generate_deployment_plan(job)
        
        logger.info(f"Executing deployment for job {job_id}")
        job.status = 'running'
        job.save()
        
        result = service.execute_deployment(job)
        
        logger.info(f"Deployment completed successfully for job {job_id}")
        return result
        
    except ObjectDoesNotExist:
        error_msg = f"DeploymentJob with id {job_id} does not exist"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    
    except DeploymentValidationError as e:
        error_msg = f"Validation failed: {str(e)}"
        logger.error(error_msg)
        try:
            job.status = 'validation_failed'
            job.plan_output = error_msg
            job.save()
        except:
            pass
        return {
            'success': False,
            'job_id': job_id,
            'error': error_msg
        }
    
    except TerraformExecutionError as e:
        error_msg = f"Terraform execution failed: {str(e)}"
        logger.error(error_msg)
        try:
            job.status = 'failed'
            job.plan_output = error_msg
            job.save()
        except:
            pass
        return {
            'success': False,
            'job_id': job_id,
            'error': error_msg
        }
    
    except Exception as e:
        error_msg = f"Deployment failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        try:
            job.status = 'failed'
            job.plan_output = f"Error: {str(e)}\n\n{traceback.format_exc()}"
            job.save()
        except:
            pass
        return {
            'success': False,
            'job_id': job_id,
            'error': error_msg
        }

def deploy_vm_demo_mode(job: DeploymentJob):
    """
    Demo mode deployment - simulates successful execution
    """
    logger.info(f"[DEMO MODE] Starting simulated deployment for job {job.id}")
    
    try:
        # Simulate planning phase
        job.status = 'pending'
        job.save()
        time.sleep(2)  # Simulate work
        
        # Generate demo plan output
        vm_names = [f"{job.vm_name}-{i+1:02d}" for i in range(job.vm_count)]
        
        plan_output = f"""[DEMO MODE] Terraform Plan
Generated at: {datetime.now().isoformat()}

Terraform will perform the following actions:

  # vsphere_virtual_machine.vm[0...{job.vm_count-1}] will be created
  + resource "vsphere_virtual_machine" "vm" {{
      + count            = {job.vm_count}
      + name             = "{job.vm_name}-XX"
      + num_cpus         = {job.cpu}
      + memory           = {job.memory}
      + datacenter       = "{job.datacenter.name}"
      + cluster          = "{job.cluster.name}"
    }}

Plan: {job.vm_count} to add, 0 to change, 0 to destroy.
"""
        
        job.status = 'plan_ready'
        job.plan_output = plan_output
        job.save()
        
        logger.info(f"[DEMO MODE] Plan ready for job {job.id}")
        time.sleep(1)
        
        # Simulate apply phase
        job.status = 'running'
        job.save()
        
        # Simulate deployment time (2 seconds per VM)
        deployment_time = job.vm_count * 2
        time.sleep(deployment_time)
        
        # Generate successful outputs
        vm_ids = [f"vm-{job.id}-{i+1:03d}" for i in range(job.vm_count)]
        vm_uuids = [f"42{job.id:04d}{i+1:03d}-1234-5678-90ab-cdef12345678" for i in range(job.vm_count)]
        vm_ips = [f"192.168.1.{100 + i}" for i in range(job.vm_count)]
        
        outputs = {
            "vm_ids": {"value": vm_ids},
            "vm_names": {"value": vm_names},
            "vm_uuids": {"value": vm_uuids},
            "vm_default_ips": {"value": vm_ips},
            "deployment_summary": {
                "value": {
                    "vm_count": job.vm_count,
                    "total_cpu": job.vm_count * job.cpu,
                    "total_memory": job.vm_count * job.memory,
                    "datacenter": job.datacenter.name,
                    "cluster": job.cluster.name,
                    "network": job.network.name,
                    "deployment_time": f"{deployment_time}s"
                }
            }
        }
        
        # Update job with success
        job.status = 'completed'
        job.plan_output = json.dumps(outputs, indent=2)
        job.save()
        
        logger.info(f"[DEMO MODE] Deployment completed successfully for job {job.id}")
        
        return {
            'success': True,
            'job_id': job.id,
            'status': 'completed',
            'outputs': outputs,
            'demo_mode': True,
            'message': 'Demo deployment completed successfully'
        }
        
    except Exception as e:
        logger.error(f"[DEMO MODE] Demo deployment failed: {str(e)}")
        job.status = 'failed'
        job.plan_output = f"Demo mode error: {str(e)}"
        job.save()
        
        return {
            'success': False,
            'job_id': job.id,
            'error': str(e)
        }


@shared_task
def generate_deployment_plan_task(job_id: int):
    try:
        job = DeploymentJob.objects.get(id=job_id)

        if DEMO_MODE:
            return generate_plan_demo_mode(job)
        
        service = DeploymentService()
        
        logger.info(f"Generating plan for job {job_id}")
        
        result = service.generate_deployment_plan(job)
        
        logger.info(f"Plan generated successfully for job {job_id}")
        return result
        
    except ObjectDoesNotExist:
        error_msg = f"DeploymentJob with id {job_id} does not exist"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    
    except Exception as e:
        error_msg = f"Plan generation failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        try:
            job.status = 'plan_failed'
            job.plan_output = error_msg
            job.save()
        except:
            pass
        return {
            'success': False,
            'job_id': job_id,
            'error': error_msg
        }

def generate_plan_demo_mode(job: DeploymentJob):
    """
    Demo mode plan generation
    """
    logger.info(f"[DEMO MODE] Generating simulated plan for job {job.id}")
    
    try:
        time.sleep(2)  # Simulate plan generation time
        
        vm_names = [f"{job.vm_name}-{i+1:02d}" for i in range(job.vm_count)]
        
        plan_output = f"""[DEMO MODE] Terraform Plan
Generated at: {datetime.now().isoformat()}

Terraform will perform the following actions:

  # vsphere_virtual_machine.vm[0...{job.vm_count-1}] will be created
  + resource "vsphere_virtual_machine" "vm" {{
      + count            = {job.vm_count}
      + name             = "{job.vm_name}-XX"
      + num_cpus         = {job.cpu}
      + memory           = {job.memory}
      + datastore        = "{job.datastore}"
      
      + network_interface {{
          + network_id = "network-demo-123"
        }}
      
      + disk {{
          + label = "disk0"
          + size  = 20
        }}
    }}

Plan: {job.vm_count} to add, 0 to change, 0 to destroy.

Expected outputs:
  + vm_ids            = (known after apply)
  + vm_names          = {json.dumps(vm_names)}
  + vm_uuids          = (known after apply)
  + deployment_summary = {{
      + vm_count      = {job.vm_count}
      + total_cpu     = {job.vm_count * job.cpu}
      + total_memory  = {job.vm_count * job.memory}
      + datacenter    = "{job.datacenter.name}"
      + cluster       = "{job.cluster.name}"
    }}

[DEMO MODE] This is a simulated plan for demonstration purposes.
No real infrastructure will be created.
"""
        
        job.status = 'plan_ready'
        job.plan_output = plan_output
        job.minio_object = f"demo_job_{job.id}"
        job.save()
        
        logger.info(f"[DEMO MODE] Plan generated successfully for job {job.id}")
        
        return {
            'success': True,
            'job_id': job.id,
            'plan_output': plan_output,
            'demo_mode': True
        }
        
    except Exception as e:
        logger.error(f"[DEMO MODE] Plan generation failed: {str(e)}")
        job.status = 'plan_failed'
        job.plan_output = f"Demo mode error: {str(e)}"
        job.save()
        
        return {
            'success': False,
            'job_id': job.id,
            'error': str(e)
        }


@shared_task
def destroy_deployment_task(job_id: int):
    """
    Task to destroy a deployment
    """
    try:
        job = DeploymentJob.objects.get(id=job_id)
        service = DeploymentService()
        
        logger.info(f"Destroying deployment for job {job_id}")
        
        result = service.destroy_deployment(job)
        
        logger.info(f"Deployment destroyed successfully for job {job_id}")
        return result
        
    except ObjectDoesNotExist:
        error_msg = f"DeploymentJob with id {job_id} does not exist"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    
    except Exception as e:
        error_msg = f"Destroy failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'job_id': job_id,
            'error': error_msg
        }

@shared_task
def sync_vsphere_inventory():
    from app.vsphere_sync import vSphereSyncService
    
    logger.info("Starting periodic vSphere inventory sync")
    
    try:
        sync_service = vSphereSyncService()
        results = sync_service.sync_all()
        
        logger.info(f"Inventory sync completed: {results}")
        return {
            'success': True,
            'results': results
        }
    except Exception as e:
        logger.error(f"Inventory sync failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
