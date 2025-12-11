from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import CollectionRecord
from .serializers import (
    CollectionRecordListSerializer,
    CollectionRecordDetailSerializer,
    CollectionRecordCreateSerializer,
    CollectionRecordUpdateSerializer,
    CollectionRecordBulkCreateSerializer,
    CollectionRecordStatsSerializer,
)


class CollectionRecordViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing waste collection records.

    Provides CRUD operations, workflow endpoints (start/complete), bulk creation,
    and statistics aggregation. All endpoints require authentication.
    """

    queryset = CollectionRecord.objects.select_related(
        'client', 'client__user', 'collector', 'collector__user', 'route', 'route_stop'
    )

    def get_serializer_class(self):
        if self.action == 'list':
            return CollectionRecordListSerializer
        elif self.action == 'retrieve':
            return CollectionRecordDetailSerializer
        elif self.action == 'create':
            return CollectionRecordCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CollectionRecordUpdateSerializer
        return CollectionRecordDetailSerializer

    def get_queryset(self):
        """
        Filtering supported by query params:
        - client_id, collector_id, route_id
        - status, collection_type
        - start_date & end_date (scheduled_date range)
        """
        qs = super().get_queryset()
        params = self.request.query_params

        if client_id := params.get('client_id'):
            qs = qs.filter(client_id=client_id)
        if collector_id := params.get('collector_id'):
            qs = qs.filter(collector_id=collector_id)
        if route_id := params.get('route_id'):
            qs = qs.filter(route_id=route_id)
        if status_param := params.get('status'):
            qs = qs.filter(status=status_param)
        if collection_type := params.get('collection_type'):
            qs = qs.filter(collection_type=collection_type)
        if params.get('start_date') and params.get('end_date'):
            qs = qs.filter(scheduled_date__range=[params['start_date'], params['end_date']])

        return qs

    # --------------------------
    # LIST
    # --------------------------
    @swagger_auto_schema(
        operation_summary="List all collections",
        operation_description="Retrieve a list of all collection records with optional filtering.",
        manual_parameters=[
            openapi.Parameter('client_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('collector_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('route_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('collection_type', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
        ],
        responses={200: CollectionRecordListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # --------------------------
    # RETRIEVE
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Retrieve a specific collection",
        responses={200: CollectionRecordDetailSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # --------------------------
    # CREATE
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Create a new collection",
        request_body=CollectionRecordCreateSerializer,
        responses={201: CollectionRecordDetailSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # --------------------------
    # UPDATE
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Update a collection",
        request_body=CollectionRecordUpdateSerializer,
        responses={200: CollectionRecordDetailSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update a collection",
        request_body=CollectionRecordUpdateSerializer,
        responses={200: CollectionRecordDetailSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # --------------------------
    # DESTROY (CANCEL)
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Cancel a collection",
        responses={200: "Collection cancelled successfully"}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'pending':
            return Response({"error": "Can only cancel pending collections."}, status=400)
        instance.status = 'cancelled'
        instance.save()
        return Response({"message": "Collection cancelled successfully"}, status=200)

    # --------------------------
    # BULK CREATE
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Bulk create collections",
        request_body=CollectionRecordBulkCreateSerializer,
        responses={201: CollectionRecordListSerializer(many=True)}
    )
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = CollectionRecordBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collections = serializer.save()
        return Response(CollectionRecordListSerializer(collections, many=True).data, status=201)

    # --------------------------
    # START COLLECTION
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Start a collection",
        responses={200: CollectionRecordDetailSerializer()}
    )
    @action(detail=True, methods=['post'])
    def start_collection(self, request, pk=None):
        collection = self.get_object()
        if collection.status != 'pending':
            return Response({"error": "Can only start pending collections"}, status=400)

        collection.collection_start = timezone.now()
        collection.status = 'in_progress'
        collection.save()

        if collection.route_stop:
            collection.route_stop.status = 'in_progress'
            collection.route_stop.actual_start = timezone.now()
            collection.route_stop.save()

        return Response(CollectionRecordDetailSerializer(collection).data)

    # --------------------------
    # COMPLETE COLLECTION
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Complete a collection",
        request_body=CollectionRecordUpdateSerializer,
        responses={200: CollectionRecordDetailSerializer()}
    )
    @action(detail=True, methods=['post'])
    def complete_collection(self, request, pk=None):
        collection = self.get_object()
        serializer = CollectionRecordUpdateSerializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        serializer.validated_data['collection_end'] = timezone.now()
        serializer.validated_data['status'] = 'completed'
        serializer.save()

        if collection.route_stop:
            collection.route_stop.status = 'completed'
            collection.route_stop.actual_end = timezone.now()
            collection.route_stop.save()

        return Response(CollectionRecordDetailSerializer(collection).data)

    # --------------------------
    # STATS
    # --------------------------
    @swagger_auto_schema(
        operation_summary="Get collection statistics",
        responses={200: CollectionRecordStatsSerializer()}
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        stats = qs.aggregate(
            total_collections=Count('collection_id'),
            completed=Count('collection_id', filter=Q(status='completed')),
            skipped=Count('collection_id', filter=Q(status='skipped')),
            pending=Count('collection_id', filter=Q(status='pending')),
            cancelled=Count('collection_id', filter=Q(status='cancelled')),
            rejected=Count('collection_id', filter=Q(status='rejected')),
            total_bags=Sum('bag_count'),
            avg_segregation_score=Avg('segregation_score'),
            avg_duration_minutes=Avg('duration_minutes'),
        )
        return Response(stats)
