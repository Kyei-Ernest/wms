# collections/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
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
    
    This ViewSet provides comprehensive CRUD operations for collection records,
    including specialized endpoints for real-time collection workflows, bulk operations,
    and performance analytics.
    
    ## Features
    - **CRUD Operations**: Create, read, update, and delete collection records
    - **Real-time Tracking**: Start and complete collections with timestamps
    - **Bulk Operations**: Create multiple collections for entire routes
    - **Analytics**: Statistics and performance metrics
    - **Filtering**: Advanced filtering by client, collector, route, status, and date range
    
    ## Authentication
    All endpoints require authentication via JWT token or session authentication.
    
    ## Code Examples
    
    ### Python/Requests Example
```python
    import requests
    
    # Setup
    BASE_URL = "https://api.wastemanagement.com/api"
    headers = {
        "Authorization": "Bearer YOUR_JWT_TOKEN",
        "Content-Type": "application/json"
    }
    
    # Create a collection
    data = {
        "client": 5,
        "collector": 3,
        "route": 10,
        "collection_type": "scheduled",
        "scheduled_date": "2025-12-05",
        "bag_count": 3,
        "waste_type": "mixed"
    }
    response = requests.post(f"{BASE_URL}/collections/", json=data, headers=headers)
    collection = response.json()
    
    # Get today's collections
    response = requests.get(f"{BASE_URL}/collections/today/", headers=headers)
    collections = response.json()
```
    
    ### JavaScript/Fetch Example
```javascript
    // Setup
    const BASE_URL = 'https://api.wastemanagement.com/api';
    const headers = {
        'Authorization': 'Bearer YOUR_JWT_TOKEN',
        'Content-Type': 'application/json'
    };
    
    // Create a collection
    const createCollection = async () => {
        const data = {
            client: 5,
            collector: 3,
            route: 10,
            collection_type: 'scheduled',
            scheduled_date: '2025-12-05',
            bag_count: 3,
            waste_type: 'mixed'
        };
        
        const response = await fetch(`${BASE_URL}/collections/`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        
        const collection = await response.json();
        console.log('Created:', collection);
    };
    
    // Get today's collections
    const getTodayCollections = async () => {
        const response = await fetch(`${BASE_URL}/collections/today/`, {
            headers: headers
        });
        const collections = await response.json();
        console.log('Today:', collections);
    };
```
    
    ### Mobile App (React Native) Example
```javascript
    import axios from 'axios';
    
    const API = axios.create({
        baseURL: 'https://api.wastemanagement.com/api',
        headers: {
            'Authorization': `Bearer ${TOKEN}`,
            'Content-Type': 'application/json'
        }
    });
    
    // Start collection (Collector mobile app)
    const startCollection = async (collectionId) => {
        try {
            const response = await API.post(`/collections/${collectionId}/start_collection/`);
            return response.data;
        } catch (error) {
            console.error('Error starting collection:', error);
        }
    };
    
    // Complete collection with photos
    const completeCollection = async (collectionId, data) => {
        const formData = new FormData();
        formData.append('bag_count', data.bagCount);
        formData.append('segregation_score', data.segregationScore);
        formData.append('gps_latitude', data.latitude);
        formData.append('gps_longitude', data.longitude);
        
        if (data.photoAfter) {
            formData.append('photo_after', {
                uri: data.photoAfter,
                type: 'image/jpeg',
                name: 'collection_after.jpg'
            });
        }
        
        try {
            const response = await API.post(
                `/collections/${collectionId}/complete_collection/`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                }
            );
            return response.data;
        } catch (error) {
            console.error('Error completing collection:', error);
        }
    };
```
    
    ### cURL Examples
```bash
    # List all collections
    curl -X GET "https://api.wastemanagement.com/api/collections/" \\
         -H "Authorization: Bearer YOUR_JWT_TOKEN"
    
    # Filter collections by collector
    curl -X GET "https://api.wastemanagement.com/api/collections/?collector_id=3" \\
         -H "Authorization: Bearer YOUR_JWT_TOKEN"
    
    # Create a collection
    curl -X POST "https://api.wastemanagement.com/api/collections/" \\
         -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
         -H "Content-Type: application/json" \\
         -d '{
             "client": 5,
             "collector": 3,
             "collection_type": "scheduled",
             "scheduled_date": "2025-12-05",
             "bag_count": 3
         }'
    
    # Start a collection
    curl -X POST "https://api.wastemanagement.com/api/collections/123/start_collection/" \\
         -H "Authorization: Bearer YOUR_JWT_TOKEN"
    
    # Complete a collection
    curl -X POST "https://api.wastemanagement.com/api/collections/123/complete_collection/" \\
         -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
         -H "Content-Type: application/json" \\
         -d '{
             "bag_count": 3,
             "segregation_score": 85,
             "gps_latitude": 5.5580,
             "gps_longitude": -0.1720,
             "notes": "All waste properly segregated"
         }'
```
    """
    
    queryset = CollectionRecord.objects.all()
    #permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
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
        Filter queryset based on query parameters.
        
        Supports filtering by:
        - client_id: Filter by specific client
        - collector_id: Filter by specific collector
        - route_id: Filter by specific route
        - status: Filter by collection status
        - collection_type: Filter by collection type
        - start_date & end_date: Filter by date range
        """
        queryset = CollectionRecord.objects.select_related(
            'client',
            'client__user',
            'collector',
            'collector__user',
            'route',
            'route_stop'
        )
        
        # Filter by client
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        # Filter by collector
        collector_id = self.request.query_params.get('collector_id')
        if collector_id:
            queryset = queryset.filter(collector_id=collector_id)
        
        # Filter by route
        route_id = self.request.query_params.get('route_id')
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by collection type
        collection_type = self.request.query_params.get('collection_type')
        if collection_type:
            queryset = queryset.filter(collection_type=collection_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(
                scheduled_date__range=[start_date, end_date]
            )
        
        return queryset
    
    @swagger_auto_schema(
        operation_summary="List all collections",
        operation_description="""
        Retrieve a list of all collection records with optional filtering.
        
        **Filters:**
        - `client_id`: Filter by client ID
        - `collector_id`: Filter by collector ID
        - `route_id`: Filter by route ID
        - `status`: Filter by status (pending, collected, missed, rejected, etc.)
        - `collection_type`: Filter by type (scheduled, on_demand, emergency)
        - `start_date` & `end_date`: Filter by date range (format: YYYY-MM-DD)
        
        **Example:**
```
        GET /api/collections/?collector_id=3&status=collected&start_date=2025-12-01&end_date=2025-12-31
```
        """,
        manual_parameters=[
            openapi.Parameter('client_id', openapi.IN_QUERY, description="Filter by client ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('collector_id', openapi.IN_QUERY, description="Filter by collector ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('route_id', openapi.IN_QUERY, description="Filter by route ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('status', openapi.IN_QUERY, description="Filter by status", type=openapi.TYPE_STRING),
            openapi.Parameter('collection_type', openapi.IN_QUERY, description="Filter by collection type", type=openapi.TYPE_STRING),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
        ],
        responses={
            200: CollectionRecordListSerializer(many=True),
            401: "Unauthorized - Invalid or missing authentication token"
        }
    )
    def list(self, request, *args, **kwargs):
        """List collections with filtering"""
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Retrieve a specific collection",
        operation_description="""
        Get detailed information about a specific collection record.
        
        **Returns:**
        - Full collection details including client info, collector info, photos, GPS data, etc.
        - Duration in minutes (if collection has started and ended)
        - Volume description (human-readable format)
        - Location verification status
        
        **Example Response:**
```json
        {
            "collection_id": 123,
            "client_name": "John Doe",
            "collector_name": "Kwame Mensah",
            "bag_count": 3,
            "segregation_score": 85,
            "status": "collected",
            "duration_minutes": 5,
            "volume_description": "3 bags, ~240L",
            "location_verified": true
        }
```
        """,
        responses={
            200: CollectionRecordDetailSerializer(),
            404: "Not Found - Collection does not exist",
            401: "Unauthorized"
        }
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific collection"""
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Create a new collection",
        operation_description="""
        Create a new collection record.
        
        **Required Fields:**
        - `client`: Client ID
        - `collection_type`: Type of collection (scheduled, on_demand, emergency)
        - `scheduled_date`: Scheduled collection date
        
        **Optional Fields:**
        - `collector`: Collector ID (required if status is not 'pending')
        - `route`: Route ID (for scheduled collections)
        - `route_stop`: Route stop ID
        - `bag_count`, `bin_size_liters`, `estimated_volume_liters`
        - `waste_type`: Type of waste
        - `photo_before`, `photo_after`
        - `segregation_score`: Quality score (0-100)
        - `gps_latitude`, `gps_longitude`
        - `notes`
        
        **Validation Rules:**
        - Collections linked to routes must be 'scheduled' type
        - Non-pending collections must have a collector assigned
        - Collected status requires waste quantity data (bags or bin size)
        
        **Example Request:**
```json
        {
            "client": 5,
            "collector": 3,
            "route": 10,
            "route_stop": 45,
            "collection_type": "scheduled",
            "scheduled_date": "2025-12-05",
            "bag_count": 3,
            "waste_type": "mixed",
            "status": "pending"
        }
```
        """,
        request_body=CollectionRecordCreateSerializer,
        responses={
            201: CollectionRecordDetailSerializer(),
            400: "Bad Request - Validation errors",
            401: "Unauthorized"
        }
    )
    def create(self, request, *args, **kwargs):
        """Create a new collection"""
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Update a collection",
        operation_description="""
        Update an existing collection record (full update).
        
        **Updatable Fields:**
        - `collector`, `bag_count`, `bin_size_liters`, `estimated_volume_liters`
        - `waste_type`, `photo_before`, `photo_after`
        - `segregation_score`, `status`
        - `gps_latitude`, `gps_longitude`, `notes`
        
        **Status Transition Rules:**
        - Cannot change from 'collected' back to 'pending'
        - Cannot change from 'collected' to 'missed' or 'skipped'
        - Changing to 'collected' requires waste quantity and at least one photo
        
        **Side Effects:**
        - Changing status to 'collected' auto-updates linked route_stop to 'completed'
        - Changing status to 'missed'/'skipped' updates route_stop to 'skipped'
        - Changing status to 'rejected' updates route_stop to 'failed'
        
        **Example Request:**
```json
        {
            "bag_count": 4,
            "segregation_score": 90,
            "status": "collected",
            "gps_latitude": 5.5580,
            "gps_longitude": -0.1720,
            "notes": "Collection completed successfully"
        }
```
        """,
        request_body=CollectionRecordUpdateSerializer,
        responses={
            200: CollectionRecordDetailSerializer(),
            400: "Bad Request - Validation errors",
            404: "Not Found",
            401: "Unauthorized"
        }
    )
    def update(self, request, *args, **kwargs):
        """Full update of a collection"""
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Partially update a collection",
        operation_description="""
        Partially update a collection record (only specified fields).
        
        Same rules as full update, but only provided fields are updated.
        
        **Example Request:**
```json
        {
            "segregation_score": 95,
            "notes": "Excellent segregation today"
        }
```
        """,
        request_body=CollectionRecordUpdateSerializer,
        responses={
            200: CollectionRecordDetailSerializer(),
            400: "Bad Request",
            404: "Not Found",
            401: "Unauthorized"
        }
    )
    def partial_update(self, request, *args, **kwargs):
        """Partial update of a collection"""
        return super().partial_update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Delete (cancel) a collection",
        operation_description="""
        Soft delete a collection by changing its status to 'cancelled'.
        
        **Important:**
        - Only 'pending' collections can be deleted
        - This is a soft delete - the record is not removed from the database
        - Use status update endpoints for other status changes
        
        **Response:**
```json
        {
            "message": "Collection cancelled successfully"
        }
```
        """,
        responses={
            200: openapi.Response(
                description="Collection cancelled successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: "Bad Request - Can only delete pending collections",
            404: "Not Found",
            401: "Unauthorized"
        }
    )
    def destroy(self, request, *args, **kwargs):
        """
        Soft delete - change status to cancelled instead of actual deletion
        """
        instance = self.get_object()
        
        # Only allow deletion of pending collections
        if instance.status != 'pending':
            return Response(
                {"error": "Can only delete pending collections. Use status update for others."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.status = 'cancelled'
        instance.save()
        
        return Response(
            {"message": "Collection cancelled successfully"},
            status=status.HTTP_200_OK
        )
    
    @swagger_auto_schema(
        operation_summary="Bulk create collections",
        operation_description="""
        Create multiple collections at once for an entire route.
        
        **Use Case:**
        When a supervisor creates a route with multiple stops, this endpoint
        can be used to create all collection records in one API call.
        
        **Request Body:**
```json
        {
            "route_id": 10,
            "collections": [
                {
                    "client": 5,
                    "collector": 3,
                    "scheduled_date": "2025-12-05",
                    "bag_count": 2,
                    "waste_type": "mixed"
                },
                {
                    "client": 6,
                    "collector": 3,
                    "scheduled_date": "2025-12-05",
                    "bag_count": 3,
                    "waste_type": "mixed"
                },
                {
                    "client": 7,
                    "collector": 3,
                    "scheduled_date": "2025-12-05",
                    "bag_count": 4,
                    "waste_type": "organic"
                }
            ]
        }
```
        
        **Python Example:**
```python
        data = {
            "route_id": 10,
            "collections": [
                {"client": client.id, "collector": collector.id, "scheduled_date": "2025-12-05", "bag_count": 2}
                for client in route_clients
            ]
        }
        response = requests.post(f"{BASE_URL}/collections/bulk_create/", json=data, headers=headers)
```
        
        **JavaScript Example:**
```javascript
        const data = {
            route_id: 10,
            collections: routeClients.map(client => ({
                client: client.id,
                collector: collector.id,
                scheduled_date: '2025-12-05',
                bag_count: 2
            }))
        };
        
        const response = await fetch(`${BASE_URL}/collections/bulk_create/`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
```
        """,
        method='post',
        request_body=CollectionRecordBulkCreateSerializer,
        responses={
            201: CollectionRecordListSerializer(many=True),
            400: "Bad Request - Validation errors",
            401: "Unauthorized"
        }
    )
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create collections for a route
        POST /api/collections/bulk_create/
        """
        serializer = CollectionRecordBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            collections = serializer.save()
            response_serializer = CollectionRecordListSerializer(collections, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="Start a collection",
        operation_description="""
        Mark a collection as started by recording the start timestamp.
        
        **Use Case:**
        Collector arrives at client location and taps "Start Collection" in mobile app.
        
        **Behavior:**
        - Sets `collection_start` to current timestamp
        - Changes status to 'collected' (or 'in_progress' if that status exists)
        - Only works for 'pending' collections
        
        **Mobile App Example (React Native):**
```javascript
        const startCollection = async (collectionId) => {
            try {
                const response = await API.post(`/collections/${collectionId}/start_collection/`);
                Alert.alert('Success', 'Collection started');
                navigation.navigate('CollectionDetails', { collection: response.data });
            } catch (error) {
                Alert.alert('Error', error.response.data.error);
            }
        };
        
        // In your component
        <Button
            title="Start Collection"
            onPress={() => startCollection(collection.collection_id)}
        />
```
        """,
        method='post',
        responses={
            200: CollectionRecordDetailSerializer(),
            400: "Bad Request - Can only start pending collections",
            404: "Not Found",
            401: "Unauthorized"
        }
    )
    @action(detail=True, methods=['post'])
    def start_collection(self, request, pk=None):
        """
        Mark collection as started
        POST /api/collections/{id}/start_collection/
        """
        collection = self.get_object()
        
        if collection.status != 'pending':
            return Response(
                {"error": "Can only start pending collections"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        collection.collection_start = timezone.now()
        collection.status = 'collected'
        collection.save()
        
        serializer = self.get_serializer(collection)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_summary="Complete a collection",
        operation_description="""
        Mark a collection as completed with final collection data.
        
        **Use Case:**
        Collector finishes collecting waste and submits final details including
        photos, bag count, GPS location, and quality score.
        
        **Request Body:**
        - `bag_count`: Number of bags collected (required)
        - `bin_size_liters`: Bin size if applicable
        - `segregation_score`: Quality score 0-100
        - `photo_after`: Photo after collection (multipart/form-data)
        - `gps_latitude`, `gps_longitude`: GPS coordinates
        - `notes`: Any additional notes
        
        **Behavior:**
        - Sets `collection_end` to current timestamp
        - Changes status to 'collected'
        - Updates linked route_stop to 'completed'
        - Auto-calculates `collected_at` timestamp
        
        **Mobile App Example (React Native with FormData):**
```javascript
        const completeCollection = async (collectionId, data) => {
            const formData = new FormData();
            formData.append('bag_count', data.bagCount);
            formData.append('segregation_score', data.segregationScore);
            formData.append('gps_latitude', data.latitude);
            formData.append('gps_longitude', data.longitude);
            formData.append('notes', data.notes);
            
            // Add photo
            if (data.photoAfter) {
                formData.append('photo_after', {
                    uri: data.photoAfter,
                    type: 'image/jpeg',
                    name: `collection_${collectionId}_after.jpg`
                });
            }
            
            try {
                const response = await API.post(
                    `/collections/${collectionId}/complete_collection/`,
                    formData,
                    {
                        headers: {
                            'Content-Type': 'multipart/form-data'
                        }
                    }
                );
                
                Alert.alert('Success', 'Collection completed!');
                return response.data;
            } catch (error) {
                Alert.alert('Error', 'Failed to complete collection');
            }
        };
```
        
        **Python Example:**
```python
        import requests
        
        files = {
            'photo_after': open('collection_photo.jpg', 'rb')
        }
        data = {
            'bag_count': 3,
            'segregation_score': 85,
            'gps_latitude': 5.5580,
            'gps_longitude': -0.1720,
            'notes': 'All waste properly segregated'
        }
        
        response = requests.post(
            f"{BASE_URL}/collections/{collection_id}/complete_collection/",
            data=data,
            files=files,
            headers={'Authorization': f'Bearer {token}'}
        )
```
        """,
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['bag_count'],
            properties={
                'bag_count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of bags collected'),
                'bin_size_liters': openapi.Schema(type=openapi.TYPE_INTEGER, description='Bin size if applicable'),
                'segregation_score': openapi.Schema(type=openapi.TYPE_INTEGER, description='Quality score 0-100'),
                'photo_after': openapi.Schema(type=openapi.TYPE_FILE, description='Photo after collection'),
                'gps_latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description='GPS latitude'),
                'gps_longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description='GPS longitude'),
                'notes': openapi.Schema(type=openapi.TYPE_STRING, description='Additional notes'),
            }
        ),
        responses={
            200: CollectionRecordDetailSerializer(),
            400: "Bad Request - Missing required fields",
            404: "Not Found",
            401: "Unauthorized"
        }
    )
    @action(detail=True, methods=['post'])
    def complete_collection(self, request, pk=None):
        """
        Mark collection as completed with final data
        POST /api/collections/{id}/complete_collection/
        """
        collection = self.get_object()
        
        # Update with provided data
        serializer = CollectionRecordUpdateSerializer(
            collection,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.validated_data['collection_end'] = timezone.now()
            serializer.validated_data['status'] = 'collected'
            serializer.save()
            
            response_serializer = CollectionRecordDetailSerializer(collection)
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="Get collection statistics",
        operation_description="""
        Retrieve aggregated statistics for collections.
        
        **Query Parameters:**
        - `start_date`: Start date for statistics (YYYY-MM-DD)
        - `end_date`: End date for statistics (YYYY-MM-DD)
        - `collector_id`: Filter by specific collector
        - `client_id`: Filter by specific client
        
        **Returns:**
        - Total collections
        - Count by status (collected, missed, pending, rejected)
        - Total bags collected
        - Average segregation score
        - Average collection duration in minutes
        
        **Response Example:**
```json
        {
            "total_collections": 150,
            "collected": 135,
            "missed": 8,
            "pending": 5,
            "rejected": 2,
            "total_bags": 450,
            "avg_segregation_score": 87.5,
            "avg_duration_minutes": 5.2
        }
```
        
        **Dashboard Usage Example:**
```javascript
        // Fetch monthly statistics
        const getMonthlyStats = async (year, month) => {
            const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
            const endDate = new Date(year, month, 0).toISOString().split('T')[0];
            
            const response = await fetch(
                `${BASE_URL}/collections/statistics/?start_date=${startDate}&end_date=${endDate}`,
                { headers: headers }
            );
            
            const stats = await response.json();
            
            // Display in dashboard
            updateDashboard({
                completionRate: (stats.collected / stats.total_collections * 100).toFixed(1),
                totalBags: stats.total_bags,
                avgQuality: stats.avg_segregation_score,
                avgTime: stats.avg_duration_minutes
            });
        };
```
        """,
        method='get',
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('collector_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('client_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: CollectionRecordStatsSerializer(),
            401: "Unauthorized"
        }
    )
    @action(detail=False, methods=['get'])
    
    def statistics(self, request):
        """
        Get collection statistics
        GET /api/collections/statistics/?start_date=2025-12-01&end_date=2025-12-31
        """
        queryset = self.get_queryset()
        
        stats = queryset.aggregate(
            total_collections=Count('collection_id'),
            collected=Count('collection_id', filter=Q(status='collected')),
            missed=Count('collection_id', filter=Q(status='missed')),
            pending=Count('collection_id', filter=Q(status='pending')),
            rejected=Count('collection_id', filter=Q(status='rejected')),
            total_bags=Sum('bag_count'),
            avg_segregation_score=Avg('segregation_score'),
        )
        
        # Calculate average duration
        collections_with_duration = queryset.exclude(
            collection_start__isnull=True
        ).exclude(
            collection_end__isnull=True
        )
        
        total_duration = 0
        count = 0
        for collection in collections_with_duration:
            duration = collection.get_duration_minutes()
            if duration:
                total_duration += duration
                count += 1
        
        stats['avg_duration_minutes'] = total_duration / count if count > 0 else 0
        
        serializer = CollectionRecordStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's collections
        GET /api/collections/today/
        """
        today = timezone.now().date()
        queryset = self.get_queryset().filter(scheduled_date=today)
        
        serializer = CollectionRecordListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def collector_performance(self, request):
        """
        Get performance metrics for a collector
        GET /api/collections/collector_performance/?collector_id=1&days=30
        """
        collector_id = request.query_params.get('collector_id')
        days = int(request.query_params.get('days', 30))
        
        if not collector_id:
            return Response(
                {"error": "collector_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_date = timezone.now().date() - timedelta(days=days)
        
        collections = CollectionRecord.objects.filter(
            collector_id=collector_id,
            scheduled_date__gte=start_date
        )
        
        stats = collections.aggregate(
            total=Count('collection_id'),
            collected=Count('collection_id', filter=Q(status='collected')),
            missed=Count('collection_id', filter=Q(status='missed')),
            avg_segregation=Avg('segregation_score'),
            total_bags=Sum('bag_count'),
        )
        
        stats['completion_rate'] = (
            (stats['collected'] / stats['total'] * 100)
            if stats['total'] > 0 else 0
        )
        
        return Response(stats)