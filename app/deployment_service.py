import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

from django.conf import settings
from django.db import transaction
from jinja2 import Template

from app.minio_client import upload_to_minio, download_from_minio
from app.models import DeploymentJob

logger = logging.getLogger(__name__)


class DeploymentValidationError(Exception):
    """Raised when deployment validation fails"""
    pass


class TerraformExecutionError(Exception):
    """Raised when Terraform execution fails"""
    pass


class DeploymentService:
    """Service for managing VM deployments with Terraform"""
    
    def __init__(self):
        self.template_path = Path(settings.BASE_DIR) / "app" / "terraform_templates" / "vsphere_vm.tf.j2"
        self.minio_bucket = "terraform-jobs"
    
    # ==================== Validation ====================
    
    def validate_deployment(self, job: DeploymentJob) -> Tuple[bool, Dict]:
        """
        Validate deployment job configuration
        
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        errors = {}
        
        # Validate VM count
        if job.vm_count < 1:
            errors['vm_count'] = "VM count must be at least 1"
        elif job.vm_count > 50:
            errors['vm_count'] = "VM count cannot exceed 50"
        
        # Validate CPU
        if job.cpu < 1:
            errors['cpu'] = "CPU count must be at least 1"
        elif job.cpu > 32:
            errors['cpu'] = "CPU count cannot exceed 32"
        
        # Validate memory
        if job.memory < 512:
            errors['memory'] = "Memory must be at least 512 MB"
        elif job.memory > 65536:
            errors['memory'] = "Memory cannot exceed 64 GB"
        
        # Validate VM name
        if not job.vm_name or len(job.vm_name) < 3:
            errors['vm_name'] = "VM name must be at least 3 characters"
        elif len(job.vm_name) > 80:
            errors['vm_name'] = "VM name cannot exceed 80 characters"
        
        # Validate required relationships
        if not job.datacenter:
            errors['datacenter'] = "Datacenter is required"
        
        if not job.cluster:
            errors['cluster'] = "Cluster is required"
        
        if not job.network:
            errors['network'] = "Network is required"
        
        # Validate datastore name
        if not job.datastore:
            errors['datastore'] = "Datastore name is required"
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info(f"Validation passed for job {job.id}: {job.name}")
        else:
            logger.warning(f"Validation failed for job {job.id}: {errors}")
        
        return is_valid, errors
    
    # ==================== VM Name Generation ====================
    
    def generate_vm_names(self, base_name: str, count: int) -> list:
        """
        Generate unique VM names
        
        Args:
            base_name: Base name for VMs
            count: Number of VMs
            
        Returns:
            List of generated VM names
        """
        names = []
        for i in range(1, count + 1):
            # Format: base_name-01, base_name-02, etc.
            name = f"{base_name}-{i:02d}"
            names.append(name)
        
        logger.info(f"Generated {len(names)} VM names: {names}")
        return names
    
    # ==================== Terraform Configuration ====================
    
    def generate_terraform_config(self, job: DeploymentJob) -> Dict[str, str]:
        """
        Generate Terraform configuration files from template
        
        Args:
            job: DeploymentJob instance
            
        Returns:
            Dictionary of filename -> content
        """
        logger.info(f"Generating Terraform config for job {job.id}")
        
        # Load template
        with open(self.template_path, 'r') as f:
            template = Template(f.read())
        
        # Prepare template context
        context = {
            'vsphere_user': settings.VSPHERE_USER,
            'vsphere_password': settings.VSPHERE_PASSWORD,
            'vsphere_server': settings.VSPHERE_SERVER,
            'datacenter': job.datacenter.name,
            'cluster': job.cluster.name,
            'network': job.network.name,
            'datastore': job.datastore,
            'vm_name': job.vm_name,
            'vm_count': job.vm_count,
            'cpu': job.cpu,
            'memory': job.memory,
            'deployment_id': job.id,
            'simulator': settings.VSPHERE_SIMULATOR,
        }
        
        # Render main Terraform file
        main_tf = template.render(**context)
        
        # Create tfvars file
        tfvars = self._generate_tfvars(job)
        
        # Create variables file (optional, for documentation)
        variables_tf = self._generate_variables_file()
        
        config_files = {
            'main.tf': main_tf,
            'terraform.tfvars': tfvars,
            'variables.tf': variables_tf,
        }
        
        logger.info(f"Generated {len(config_files)} Terraform files")
        return config_files
    
    def _generate_tfvars(self, job: DeploymentJob) -> str:
        """Generate terraform.tfvars file"""
        tfvars = f"""# Terraform Variables for Job {job.id}
# Generated at: {datetime.now().isoformat()}

# vSphere Connection
vsphere_user             = "{settings.VSPHERE_USER}"
vsphere_password         = "{settings.VSPHERE_PASSWORD}"
vsphere_server           = "{settings.VSPHERE_SERVER}"
allow_unverified_ssl     = true

# Infrastructure
datacenter = "{job.datacenter.name}"
cluster    = "{job.cluster.name}"
network    = "{job.network.name}"
datastore  = "{job.datastore}"

# VM Configuration
vm_name    = "{job.vm_name}"
vm_count   = {job.vm_count}
cpu        = {job.cpu}
memory     = {job.memory}
disk_size  = 20
guest_id   = "otherLinux64Guest"
firmware   = "bios"

# Tags
tags = {{
  "deployment_id" = "{job.id}"
  "created_by"    = "terraform"
  "environment"   = "development"
}}
"""
        return tfvars
    
    def _generate_variables_file(self) -> str:
        """Generate variables.tf file for documentation"""
        return """# Variables are defined in the main template
# This file is generated for reference only
"""
    
    # ==================== MinIO Operations ====================
    
    def upload_config_to_minio(self, job: DeploymentJob, config_files: Dict[str, str]) -> str:
        """
        Upload Terraform configuration files to MinIO
        
        Args:
            job: DeploymentJob instance
            config_files: Dictionary of filename -> content
            
        Returns:
            MinIO object prefix
        """
        object_prefix = f"job_{job.id}"
        
        logger.info(f"Uploading Terraform config to MinIO: {object_prefix}")
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Write files to temp directory
            for filename, content in config_files.items():
                file_path = tmpdir_path / filename
                with open(file_path, 'w') as f:
                    f.write(content)
                
                # Upload to MinIO
                object_name = f"{object_prefix}/{filename}"
                upload_to_minio(self.minio_bucket, str(file_path), object_name)
                logger.info(f"Uploaded {object_name} to MinIO")
        
        return object_prefix
    
    def download_config_from_minio(self, job: DeploymentJob, target_dir: Path) -> None:
        """
        Download Terraform configuration from MinIO
        
        Args:
            job: DeploymentJob instance
            target_dir: Directory to download files to
        """
        object_prefix = job.minio_object
        
        if not object_prefix:
            raise ValueError(f"Job {job.id} has no MinIO object reference")
        
        logger.info(f"Downloading Terraform config from MinIO: {object_prefix}")
        
        # List of expected files
        files = ['main.tf', 'terraform.tfvars', 'variables.tf']
        
        for filename in files:
            object_name = f"{object_prefix}/{filename}"
            local_path = target_dir / filename
            
            try:
                download_from_minio(self.minio_bucket, object_name, str(local_path))
                logger.info(f"Downloaded {object_name} from MinIO")
            except Exception as e:
                logger.error(f"Failed to download {object_name}: {e}")
                raise
    
    # ==================== Terraform Execution ====================
    
    def run_terraform_init(self, work_dir: Path) -> subprocess.CompletedProcess:
        """Run terraform init"""
        logger.info(f"Running terraform init in {work_dir}")
        
        result = subprocess.run(
            ['terraform', 'init', '-no-color'],
            cwd=work_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Terraform init failed: {result.stderr}")
            raise TerraformExecutionError(f"Init failed: {result.stderr}")
        
        logger.info("Terraform init completed successfully")
        return result
    
    def run_terraform_plan(self, work_dir: Path) -> Tuple[subprocess.CompletedProcess, str]:
        """
        Run terraform plan
        
        Returns:
            Tuple of (result, plan_output)
        """
        logger.info(f"Running terraform plan in {work_dir}")
        
        result = subprocess.run(
            ['terraform', 'plan', '-no-color', '-out=tfplan'],
            cwd=work_dir,
            capture_output=True,
            text=True
        )
        
        plan_output = result.stdout
        
        if result.returncode != 0:
            logger.error(f"Terraform plan failed: {result.stderr}")
            raise TerraformExecutionError(f"Plan failed: {result.stderr}")
        
        logger.info("Terraform plan completed successfully")
        return result, plan_output
    
    def run_terraform_apply(self, work_dir: Path) -> Tuple[subprocess.CompletedProcess, Dict]:
        """
        Run terraform apply
        
        Returns:
            Tuple of (result, outputs)
        """
        logger.info(f"Running terraform apply in {work_dir}")
        
        result = subprocess.run(
            ['terraform', 'apply', '-no-color', '-auto-approve', 'tfplan'],
            cwd=work_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Terraform apply failed: {result.stderr}")
            raise TerraformExecutionError(f"Apply failed: {result.stderr}")
        
        # Get outputs
        outputs = self._get_terraform_outputs(work_dir)
        
        logger.info("Terraform apply completed successfully")
        return result, outputs
    
    def run_terraform_destroy(self, work_dir: Path) -> subprocess.CompletedProcess:
        """Run terraform destroy"""
        logger.info(f"Running terraform destroy in {work_dir}")
        
        result = subprocess.run(
            ['terraform', 'destroy', '-no-color', '-auto-approve'],
            cwd=work_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Terraform destroy failed: {result.stderr}")
            raise TerraformExecutionError(f"Destroy failed: {result.stderr}")
        
        logger.info("Terraform destroy completed successfully")
        return result
    
    def _get_terraform_outputs(self, work_dir: Path) -> Dict:
        """Get Terraform outputs as JSON"""
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            cwd=work_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.warning("Failed to parse Terraform outputs")
                return {}
        
        return {}
    
    # ==================== Workflow Methods ====================
    
    @transaction.atomic
    def create_deployment_job(self, job: DeploymentJob) -> Dict:
        """
        Step 1: Validate and create deployment job
        Following activity diagram workflow
        """
        logger.info(f"Creating deployment job: {job.name}")
        
        # Validate input
        is_valid, errors = self.validate_deployment(job)
        
        if not is_valid:
            job.status = 'validation_failed'
            job.plan_output = json.dumps({'errors': errors}, indent=2)
            job.save()
            raise DeploymentValidationError(errors)
        
        # Generate VM names
        vm_names = self.generate_vm_names(job.vm_name, job.vm_count)
        
        # Set status to pending
        job.status = 'pending'
        job.save()
        
        return {
            'success': True,
            'job_id': job.id,
            'vm_names': vm_names,
            'status': job.status
        }
    
    def generate_deployment_plan(self, job: DeploymentJob) -> Dict:
        """
        Step 2: Generate Terraform plan
        """
        logger.info(f"Generating deployment plan for job {job.id}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            
            # Generate Terraform config
            config_files = self.generate_terraform_config(job)
            
            # Write files to work directory
            for filename, content in config_files.items():
                file_path = work_dir / filename
                with open(file_path, 'w') as f:
                    f.write(content)
            
            # Upload to MinIO
            object_prefix = self.upload_config_to_minio(job, config_files)
            job.minio_object = object_prefix
            job.save()
            
            # Run terraform init
            self.run_terraform_init(work_dir)
            
            # Run terraform plan
            plan_result, plan_output = self.run_terraform_plan(work_dir)
            
            # Upload plan file to MinIO
            plan_file = work_dir / 'tfplan'
            if plan_file.exists():
                upload_to_minio(
                    self.minio_bucket,
                    str(plan_file),
                    f"{object_prefix}/tfplan"
                )
            
            # Upload logs to MinIO
            logs_content = f"""Terraform Plan Logs
Generated at: {datetime.now().isoformat()}

STDOUT:
{plan_output}

STDERR:
{plan_result.stderr}
"""
            logs_file = work_dir / 'plan_logs.txt'
            with open(logs_file, 'w') as f:
                f.write(logs_content)
            
            upload_to_minio(
                self.minio_bucket,
                str(logs_file),
                f"{object_prefix}/plan_logs.txt"
            )
            
            # Update job with plan output
            job.plan_output = plan_output[:5000]  # Truncate for DB
            job.status = 'plan_ready'
            job.save()
            
            return {
                'success': True,
                'job_id': job.id,
                'plan_output': plan_output,
                'minio_object': object_prefix
            }
    
    def execute_deployment(self, job: DeploymentJob) -> Dict:
        """
        Step 3: Execute Terraform apply
        """
        logger.info(f"Executing deployment for job {job.id}")
        
        job.status = 'running'
        job.save()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            
            try:
                # Download config from MinIO
                self.download_config_from_minio(job, work_dir)
                
                # Download plan file
                plan_object = f"{job.minio_object}/tfplan"
                plan_file = work_dir / 'tfplan'
                download_from_minio(self.minio_bucket, plan_object, str(plan_file))
                
                # Run terraform init (needed after download)
                self.run_terraform_init(work_dir)
                
                # Run terraform apply
                apply_result, outputs = self.run_terraform_apply(work_dir)
                
                # Capture state file
                state_file = work_dir / 'terraform.tfstate'
                if state_file.exists():
                    upload_to_minio(
                        self.minio_bucket,
                        str(state_file),
                        f"{job.minio_object}/terraform.tfstate"
                    )
                
                # Upload apply logs
                logs_content = f"""Terraform Apply Logs
Executed at: {datetime.now().isoformat()}

STDOUT:
{apply_result.stdout}

STDERR:
{apply_result.stderr}

OUTPUTS:
{json.dumps(outputs, indent=2)}
"""
                logs_file = work_dir / 'apply_logs.txt'
                with open(logs_file, 'w') as f:
                    f.write(logs_content)
                
                upload_to_minio(
                    self.minio_bucket,
                    str(logs_file),
                    f"{job.minio_object}/apply_logs.txt"
                )
                
                # Update job
                job.status = 'completed'
                job.plan_output = json.dumps(outputs, indent=2)
                job.save()
                
                logger.info(f"Deployment completed successfully for job {job.id}")
                
                return {
                    'success': True,
                    'job_id': job.id,
                    'status': 'completed',
                    'outputs': outputs
                }
                
            except Exception as e:
                logger.error(f"Deployment failed for job {job.id}: {str(e)}")
                
                job.status = 'failed'
                job.plan_output = str(e)
                job.save()
                
                raise
    
    def destroy_deployment(self, job: DeploymentJob) -> Dict:
        """
        Destroy deployment (cleanup)
        """
        logger.info(f"Destroying deployment for job {job.id}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            
            try:
                # Download config and state from MinIO
                self.download_config_from_minio(job, work_dir)
                
                state_object = f"{job.minio_object}/terraform.tfstate"
                state_file = work_dir / 'terraform.tfstate'
                download_from_minio(self.minio_bucket, state_object, str(state_file))
                
                # Run terraform init
                self.run_terraform_init(work_dir)
                
                # Run terraform destroy
                destroy_result = self.run_terraform_destroy(work_dir)
                
                # Upload destroy logs
                logs_content = f"""Terraform Destroy Logs
Executed at: {datetime.now().isoformat()}

STDOUT:
{destroy_result.stdout}

STDERR:
{destroy_result.stderr}
"""
                logs_file = work_dir / 'destroy_logs.txt'
                with open(logs_file, 'w') as f:
                    f.write(logs_content)
                
                upload_to_minio(
                    self.minio_bucket,
                    str(logs_file),
                    f"{job.minio_object}/destroy_logs.txt"
                )
                
                # Update job
                job.status = 'destroyed'
                job.save()
                
                logger.info(f"Deployment destroyed successfully for job {job.id}")
                
                return {
                    'success': True,
                    'job_id': job.id,
                    'status': 'destroyed'
                }
                
            except Exception as e:
                logger.error(f"Destroy failed for job {job.id}: {str(e)}")
                raise