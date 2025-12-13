from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CollectionRecord
from .serializers import (
    CollectionRecordSerializer,
    CollectionRecordCreateSerializer,
)
from accounts.permissions import IsClient, IsSupervisor, IsCompanyCollector


class CollectionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for accessing and managing CollectionRecord data.

    CollectionRecord is the immutable evidence log of a waste collection event.
    It captures payment info, GPS, photos, waste quantity, and audit data.

    Role-based access:
    - Clients: can only view their own records and summaries.
    - Supervisors: can view all records tied to their company routes.
    - Collectors: can view records they created and update them with evidence.

    Endpoints exposed:
    - GET /collections/ → list records (scoped by role)
    - GET /collections/{id}/ → retrieve single record
    - GET /collections/my_summary/ → client summary stats
    - GET /collections/my_records/ → client’s own records list
    - POST /collections/{id}/update_record/ → collector updates evidence/payment
    """

    queryset = CollectionRecord.objects.all()
    serializer_class = CollectionRecordSerializer

    def get_queryset(self):
        """
        Role-based queryset filtering:
        - Client → only their own records
        - Supervisor → all records under their supervised routes
        - Collector → records they executed
        - Others → no access
        """
        user = self.request.user
        if hasattr(user, "client"):
            return CollectionRecord.objects.filter(client=user.client)
        elif hasattr(user, "supervisor"):
            return CollectionRecord.objects.filter(route__supervisor=user.supervisor)
        elif hasattr(user, "collector"):
            return CollectionRecord.objects.filter(collector=user.collector)
        return CollectionRecord.objects.none()

    @action(detail=False, methods=["get"], permission_classes=[IsClient])
    def my_summary(self, request):
        """
        GET /collections/my_summary/

        Client views aggregated stats of their own collection records.
        Useful for dashboards showing quick totals.

        Response example:
        {
          "total": 12,
          "completed": 9,
          "pending": 2,
          "skipped": 1,
          "cancelled": 0,
          "rejected": 0
        }
        """
        client = request.user.client
        qs = CollectionRecord.objects.filter(client=client)

        summary = {
            "total": qs.count(),
            "completed": qs.filter(status="completed").count(),
            "pending": qs.filter(status="pending").count(),
            "skipped": qs.filter(status="skipped").count(),
            "cancelled": qs.filter(status="cancelled").count(),
            "rejected": qs.filter(status="rejected").count(),
        }
        return Response(summary)

    @action(detail=False, methods=["get"], permission_classes=[IsClient])
    def my_records(self, request):
        """
        GET /collections/my_records/

        Client lists all their own collection records in reverse chronological order.
        Includes payment, waste, GPS, and photo evidence.

        Response example:
        [
          {
            "collection_id": 55,
            "status": "completed",
            "collection_type": "on_demand",
            "scheduled_date": "2025-12-13",
            "payment_method": "momo",
            "amount_paid": "20.00",
            "bag_count": 3,
            "bin_size_liters": 240,
            "waste_type": "mixed",
            "collected_at": "2025-12-13T08:45:00Z"
          }
        ]
        """
        client = request.user.client
        qs = CollectionRecord.objects.filter(client=client).order_by("-collected_at")
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsCompanyCollector])
    def update_record(self, request, pk=None):
        """
        POST /collections/{id}/update_record/

        Collector updates a collection record with operational evidence:
        - Payment method + amount
        - Waste quantity (bags, bin size, estimated volume)
        - Waste type
        - GPS coordinates
        - Photos (before/after)
        - Notes

        This endpoint is typically called when completing a stop.
        It marks the record as 'completed' and sets collected_at timestamp.

        Request example:
        {
          "payment_method": "momo",
          "amount_paid": "20.00",
          "bag_count": 3,
          "bin_size_liters": 240,
          "waste_type": "mixed",
          "latitude": 5.603,
          "longitude": -0.196,
          "notes": "Client paid via MoMo"
        }

        Response example:
        {
          "collection_id": 55,
          "client_name": "Ama Mensah",
          "collector_name": "Kwame Asante",
          "status": "completed",
          "payment_method": "momo",
          "amount_paid": "20.00",
          "bag_count": 3,
          "bin_size_liters": 240,
          "waste_type": "mixed",
          "latitude": 5.603,
          "longitude": -0.196,
          "notes": "Client paid via MoMo",
          "collected_at": "2025-12-13T08:45:00Z"
        }
        """
        record = self.get_object()
        serializer = CollectionRecordCreateSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status="completed", collected_at=record.collected_at or None)
        return Response(CollectionRecordSerializer(record).data, status=status.HTTP_200_OK)
