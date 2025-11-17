from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from app.models import DeploymentJob
from app.deployment_service import DeploymentService, DeploymentValidationError
from app.tasks import (
    deploy_vm_via_terraform,
    generate_deployment_plan_task,
    destroy_deployment_task
)
from app.minio_client import download_from_minio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class DeploymentJobView(APIView):
    """
    API view for creating and managing deployment jobs
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Create a new deployment job
        Step 1 of activity diagram: Validate input and create job
        """
        try:
            # Extract data from request
            data = request.data
            
            # Create deployment job instance
            job = DeploymentJob(
                name=data.get('name'),
                vm_name=data.get('vm_name'),
                vm_count=data.get('vm_count', 1),
                cpu=data.get('cpu', 2),
                memory=data.get('memory', 2048),
                datacenter_id=data.get('datacenter'),
                cluster_id=data.get('cluster'),
                network_id=data.get('network'),
                datastore=data.get('datastore', 'LocalDS_0'),
                status='pending'
            )
            
            # Validate before saving
            service = DeploymentService()
            is_valid, errors = service.validate_deployment(job)
            
            if not is_valid:
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save job
            job.save()
            
            # Generate VM names for preview
            vm_names = service.generate_vm_names(job.vm_name, job.vm_count)
            
            logger.info(f"Created deployment job {job.id}: {job.name}")
            
            return Response({
                'success': True,
                'job_id': job.id,
                'name': job.name,
                'vm_names': vm_names,
                'status': job.status,
                'message': 'Deployment job created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to create deployment job: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """List all deployment jobs"""
        try:
            jobs = DeploymentJob.objects.all().order_by('-created_at')
            
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'name': job.name,
                    'vm_name': job.vm_name,
                    'vm_count': job.vm_count,
                    'status': job.status,
                    'datacenter': job.datacenter.name if job.datacenter else None,
                    'cluster': job.cluster.name if job.cluster else None,
                    'created_at': job.created_at.isoformat(),
                })
            
            return Response({
                'success': True,
                'jobs': jobs_data,
                'count': len(jobs_data)
            })
            
        except Exception as e:
            logger.error(f"Failed to list deployment jobs: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentJobDetailView(APIView):
    """API view for individual deployment job operations"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        """Get deployment job details"""
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            return Response({
                'success': True,
                'job': {
                    'id': job.id,
                    'name': job.name,
                    'vm_name': job.vm_name,
                    'vm_count': job.vm_count,
                    'cpu': job.cpu,
                    'memory': job.memory,
                    'datastore': job.datastore,
                    'status': job.status,
                    'datacenter': job.datacenter.name if job.datacenter else None,
                    'cluster': job.cluster.name if job.cluster else None,
                    'network': job.network.name if job.network else None,
                    'minio_object': job.minio_object,
                    'plan_output': job.plan_output,
                    'created_at': job.created_at.isoformat(),
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to get deployment job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, job_id):
        """Cancel/delete a deployment job"""
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            # Can only cancel/delete if not running
            if job.status == 'running':
                return Response({
                    'success': False,
                    'error': 'Cannot delete a running deployment'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            job_name = job.name
            job.status = 'cancelled'
            job.save()
            
            logger.info(f"Cancelled deployment job {job_id}: {job_name}")
            
            return Response({
                'success': True,
                'message': f'Deployment job "{job_name}" cancelled'
            })
            
        except Exception as e:
            logger.error(f"Failed to cancel deployment job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentPlanView(APIView):
    """API view for generating Terraform plan"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        """
        Generate Terraform plan for deployment
        Step 2 of activity diagram: Generate plan and store in MinIO
        """
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            # Check if job is in valid state
            if job.status not in ['pending', 'plan_failed']:
                return Response({
                    'success': False,
                    'error': f'Cannot generate plan for job in status: {job.status}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Trigger async plan generation
            task = generate_deployment_plan_task.delay(job_id)
            
            logger.info(f"Triggered plan generation for job {job_id}, task: {task.id}")
            
            return Response({
                'success': True,
                'message': 'Plan generation started',
                'job_id': job_id,
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"Failed to generate plan for job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentExecuteView(APIView):
    """API view for executing deployment"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        """
        Execute deployment (apply Terraform)
        Step 3 of activity diagram: Apply Terraform plan
        """
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            # Check if job has a plan
            if not job.minio_object:
                return Response({
                    'success': False,
                    'error': 'No plan found. Please generate a plan first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if job is in valid state
            if job.status not in ['pending', 'plan_ready']:
                return Response({
                    'success': False,
                    'error': f'Cannot execute deployment in status: {job.status}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Trigger async deployment
            task = deploy_vm_via_terraform.delay(job_id)
            
            logger.info(f"Triggered deployment for job {job_id}, task: {task.id}")
            
            return Response({
                'success': True,
                'message': 'Deployment started',
                'job_id': job_id,
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"Failed to execute deployment for job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentDestroyView(APIView):
    """API view for destroying deployment"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        """
        Destroy deployment (terraform destroy)
        """
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            # Can only destroy completed or failed deployments
            if job.status not in ['completed', 'failed']:
                return Response({
                    'success': False,
                    'error': f'Cannot destroy deployment in status: {job.status}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Trigger async destroy
            task = destroy_deployment_task.delay(job_id)
            
            logger.info(f"Triggered destroy for job {job_id}, task: {task.id}")
            
            return Response({
                'success': True,
                'message': 'Deployment destruction started',
                'job_id': job_id,
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"Failed to destroy deployment for job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentJobLogsView(APIView):
    """API view for retrieving deployment logs"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        """
        Get deployment logs from MinIO
        """
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            if not job.minio_object:
                return Response({
                    'success': False,
                    'error': 'No logs available yet'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Determine which log file to retrieve
            log_type = request.query_params.get('type', 'apply')  # plan, apply, or destroy
            
            log_filename = f"{log_type}_logs.txt"
            object_name = f"{job.minio_object}/{log_filename}"
            
            # Download logs from MinIO
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_file:
                try:
                    download_from_minio('terraform-jobs', object_name, tmp_file.name)
                    
                    with open(tmp_file.name, 'r') as f:
                        logs = f.read()
                    
                    return Response({
                        'success': True,
                        'job_id': job_id,
                        'log_type': log_type,
                        'logs': logs
                    })
                    
                except Exception as e:
                    logger.warning(f"Logs not found: {object_name}")
                    return Response({
                        'success': False,
                        'error': f'Logs not found: {log_type}'
                    }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Failed to retrieve logs for job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeploymentStatusView(APIView):
    """API view for checking deployment status"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        """Get current deployment status"""
        try:
            job = get_object_or_404(DeploymentJob, id=job_id)
            
            # Parse outputs if available
            outputs = None
            if job.plan_output:
                try:
                    import json
                    outputs = json.loads(job.plan_output)
                except:
                    outputs = job.plan_output
            
            return Response({
                'success': True,
                'job_id': job_id,
                'name': job.name,
                'status': job.status,
                'vm_count': job.vm_count,
                'created_at': job.created_at.isoformat(),
                'outputs': outputs,
                'minio_object': job.minio_object
            })
            
        except Exception as e:
            logger.error(f"Failed to get status for job {job_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)