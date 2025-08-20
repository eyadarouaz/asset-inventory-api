import os
import tempfile
import subprocess
import traceback
import logging

from celery import shared_task
from jinja2 import Template
from django.conf import settings

from app.minio_client import upload_to_minio
from app.models import DeploymentJob

logger = logging.getLogger(__name__)


@shared_task
def deploy_vm_via_terraform(job_id):
    try:
        job = DeploymentJob.objects.get(id=job_id)
        job.status = 'running'
        job.save()

        template_path = os.path.join(
            settings.BASE_DIR, "app", "terraform_templates", "vsphere_vm.tf.j2"
        )
        logger.debug(f"Using Terraform template at: {template_path}")

        with open(template_path) as f:
            template = Template(f.read())

        tf_config = template.render(
            vsphere_user=settings.VSPHERE_USER,
            vsphere_password=settings.VSPHERE_PASSWORD,
            vsphere_server=settings.VSPHERE_SERVER,
            datacenter=job.datacenter.name,
            cluster=job.cluster.name,
            datastore=job.datastore,
            network=job.network.name,
            vm_name=job.vm_name,
            cpu=job.cpu,
            memory=job.memory,
            vm_count=job.vm_count,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tf_path = os.path.join(tmpdir, "main.tf")
            logs_path = os.path.join(tmpdir, "logs.txt")

            # Write the Terraform config file
            with open(tf_path, "w") as f:
                f.write(tf_config)

            bucket = "terraform-jobs"
            object_prefix = f"job_{job.id}"

            # Upload main.tf to MinIO
            job.minio_object = upload_to_minio(bucket, tf_path, f"{object_prefix}/main.tf")

            # Run Terraform and capture logs
            with open(logs_path, "w") as log_file:
                subprocess.run(
                    ["terraform", "init"],
                    cwd=tmpdir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=True,
                )
                subprocess.run(
                    ["terraform", "plan"],
                    cwd=tmpdir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=True,
                )

            # Upload logs.txt to MinIO
            upload_to_minio(bucket, logs_path, f"{object_prefix}/logs.txt")

            # Save part of log output to DB
            with open(logs_path) as log_file:
                job.plan_output = log_file.read()[:5000]

            job.status = 'completed'
            job.save()

            logger.info(f"Terraform deployment completed successfully for job {job.id}")
            return f"Terraform init and plan completed for job {job.id}."

    except DeploymentJob.DoesNotExist:
        error_msg = f"DeploymentJob with id {job_id} does not exist."
        logger.error(error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Deployment failed for job {job_id}: {str(e)}"
        logger.error(error_msg)
        logger.debug(traceback.format_exc())
        try:
            job.status = 'failed'
            job.save()
        except:
            pass
        return error_msg
