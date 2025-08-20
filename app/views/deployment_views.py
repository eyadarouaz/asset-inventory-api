from app.minio_client import get_file_from_minio
from app.tasks import deploy_vm_via_terraform

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.models import DeploymentJob
from app.serializers import DeploymentJobSerializer
from rest_framework.permissions import IsAuthenticated


class DeploymentJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = DeploymentJob.objects.all().order_by('-created_at')
        serializer = DeploymentJobSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        serializer = DeploymentJobSerializer(data=request.data)
        if serializer.is_valid():
            job = serializer.save(status="pending")
            deploy_vm_via_terraform.delay(job.id)
            return Response({
                "message": "Deployment started.",
                "job_id": job.id,
                "status": job.status
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeploymentJobLogsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, job_id):
        try:
            job = DeploymentJob.objects.get(id=job_id)
            bucket = "terraform-jobs"
            object_name = f"job_{job.id}/logs.txt"

            logs = get_file_from_minio(bucket, object_name)
            return Response({"logs": logs}, status=status.HTTP_200_OK)

        except DeploymentJob.DoesNotExist:
            return Response({"error": "Deployment job not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Failed to retrieve logs: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)