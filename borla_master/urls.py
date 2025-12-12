from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi



schema_view = get_schema_view(
   openapi.Info(
      title="Borla Tracker(Waste Management System)",
      default_version='v1',
      description="API documentation for the Borla Tracker (Waste Management System)",
      contact=openapi.Contact(email="ernestkyei101@gmail.com"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)




urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),

    path('api/auth/', include('accounts.urls')),
    path('api/client/', include('client.urls')),
    path('api/company/', include('waste_management_company.urls')),
    path('api/supervisor/', include('supervisor.urls')),
    path('api/collector/', include('collector.urls')),
    path('api/zones/', include('zones.urls')),
    path('api/routes/', include('routes.urls')),
    path('api/collection-records/',include('collection_management.urls')),
    path('api/on-demand-requests/', include('on_demand.urls')),
    path('api/scheduled-requests/', include('scheduled_request.urls')),



    #Swagger/OpenAPI docs
    path('api/docs/swagger(<format>\.json|\.yaml)', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('api/docs/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/docs/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # JSON/YAML schema
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
]
