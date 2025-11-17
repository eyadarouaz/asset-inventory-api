import os
import tempfile
import subprocess
import traceback
import logging

from celery import shared_task
from jinja2 import Template
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from app.deployment_service import DeploymentService, DeploymentValidationError, TerraformExecutionError
from app.minio_client import upload_to_minio
from app.models import DeploymentJob

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=0)
def deploy_vm_via_terraform(self, job_id: int):
    try:
        job = DeploymentJob.objects.get(id=job_id)
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


@shared_task
def generate_deployment_plan_task(job_id: int):
    try:
        job = DeploymentJob.objects.get(id=job_id)
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
