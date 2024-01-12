
import json
from django.http import JsonResponse
from django.conf import settings
import ee
import numpy as np
#import geemap 
import joblib
from datetime import date,timedelta
from django.shortcuts import get_object_or_404, render
import jwt
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from api.serializers import FarmSerializer, FieldSerializer, JobFieldSerializer, JobInputSerializer, JobSerializer, SeasonSerializer, FieldDataSerializer, FieldGridSerializer
from api.models import Farm, Field, Season, Field_Data, Field_Grid, Job, Job_Field, Job_Input
from collections import defaultdict
from django.db.models import F
from django.db.models import Prefetch
from datetime import datetime
from django.utils import timezone
from background_task import background



 #5*24*60*60)  #Schedule the task every 5 days (5 * 24 * 60 * 60 seconds)
@background(schedule = 1) 
def periodicNDVIUpdate():
    print("Running Periodic Ndvi Update Task")
    fields = Field.objects.all()
    for field in fields:
        fields_data = Field_Data.objects.filter(field=field.id)
        for field_data in fields_data:
            coordinates = json.loads(field_data.coordinates)
            if not coordinates:
                print('Empty coordinates object')
                return
            avgNDVI = calculate_avg_ndvi(coordinates=coordinates, startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1)))
            field_data.avg_ndvi = avgNDVI
            field_data.save()

            fields_grid = Field_Grid.objects.filter(field_data = field_data.id)
            for field_grid in fields_grid:
                #point = lat_lng.replace("'", "\"")
                
                point = field_grid.lat_lng.replace("'", "\"")
                point = json.loads(point)
                if not point:
                    print('Empty Points object')
                    return
                point_ndvi = calculate_point_ndvi(point=point, startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1)))
                field_grid.ndvi = point_ndvi
                field_grid.save()
            
    print("Periodic Ndvi Update Task Ended")

# @background()  # Schedule this task to run every 5 seconds for testing
# def schedule_next_update():
#     print('Started schedule_next_update function')
#     task_name = 'api.views.schedule_next_update'
#     existing_task = Task.objects.filter(task_name='api.views.schedule_next_update').first()
    
#     if existing_task:
#         print(f'Task with name {task_name} already exists. Not creating a new one.')
#         return
#     # Get the last execution of the task
#     last_execution = Task.objects.filter(task_name='api.views.periodicNDVIUpdate').last()
#     print("TASSSSSK NAMEE",last_execution.task_name)
#     if last_execution:
#         next_execution = last_execution.run_at + timezone.timedelta(days=5)  # Schedule next task 5 days later
#     else:
#         next_execution = timezone.now()  # Schedule the first task to run now

#     # Schedule the next execution of the task
#     Task.objects.create(
#         task_name='api.views.periodicNDVIUpdate',  # Replace with the actual task name
#         run_at=next_execution,
#     )

class FarmView(APIView):
    def get(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)

        userID = payload['id']
        queryset = Farm.objects.filter(user=userID)
        serializer = FarmSerializer(queryset, many=True)
        return Response(serializer.data)
        
    def post(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)

        request.data['user'] = payload['id']

        serializer = FarmSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class FarmDetail(APIView):
    def delete(self, request, id):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        farm = get_object_or_404(Farm, pk=id)
        farm.delete()
        return Response(status=200)
    def patch(self, request, id):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        farm = get_object_or_404(Farm, pk=id)
        serializer = FarmSerializer(farm, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

def calculate_polygon_area(coordinates):
    # Create an Earth Engine geometry from the provided coordinates
    polygon = ee.Geometry.Polygon(coordinates)

    # Calculate the area of the polygon in square meters
    area = polygon.area()

    # Convert the area from square meters to square kilometers
    area_hectares = area.divide(1e4).getInfo()
    area_hectares = round(area_hectares, 3)

    return area_hectares

def calculate_avg_ndvi(coordinates,startDate, endDate):
    #print(coordinates)
    for coord in coordinates:
        #print((coord))
        coord['lat'] = float(coord['lat'])
        coord['lng'] = float(coord['lng'])
    
    polygon_coordinates = [[coord['lng'], coord['lat']] for coord in coordinates]
    
    
    # Create a polygon geometry from the coordinates
    polygon_geometry = ee.Geometry.Polygon(polygon_coordinates)
    
    # Define Sentinel-2 image collection and filter by date
    collection = (
        ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
        .filterBounds(polygon_geometry)
        .filterDate(startDate, endDate)  
        .sort('CLOUD_COVERAGE_ASSESSMENT')
    )

    # Calculate NDVI for the collection
    def calculate_ndvi(image):
        ndvi = image.normalizedDifference(['B8', 'B4'])
        scaled_ndvi = ndvi  # Scale to the range [0, 1]
        return image.addBands(scaled_ndvi.rename('NDVI'))

    collection_with_ndvi = collection.map(calculate_ndvi)
    merged_image = collection_with_ndvi.median()
    # Calculate average NDVI for the polygon region
    average_ndvi = (
        merged_image
        .select('NDVI')
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=polygon_geometry,
            scale=10,  
            bestEffort = True
        )
        .get('NDVI')
    )
    return average_ndvi.getInfo()

def calculate_point_ndvi(point,startDate, endDate):
        
            # Create a Point geometry from the given coordinates
            point_geometry = ee.Geometry.Point(float(point['lng']), float(point['lat']))
             
            # Use Landsat 8 imagery for NDVI calculation (you can change this as needed)
            image = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
                .filterBounds(point_geometry) \
                .filterDate(startDate, endDate) \
                .sort('CLOUD_COVERAGE_ASSESSMENT') \
                .median()

            # Calculate NDVI
            ndvi = image.normalizedDifference(['B8', 'B4'])

            scaled_ndvi = ndvi

            # Get the NDVI value as a number
            ndvi_value = scaled_ndvi.reduceRegion(ee.Reducer.mean(), point_geometry, 10).get('nd')
            ndvi_value = ee.Number(ndvi_value).getInfo()
           
            return ndvi_value

def calculate_point_ndvi2(points,startDate, endDate):
            batch_points = []
            for point in points:
                batch_points.append(ee.Geometry.Point(float(point['lng']), float(point['lat'])))
            feature_collection = ee.FeatureCollection(batch_points)

            
             
            # Use Landsat 8 imagery for NDVI calculation (you can change this as needed)
            image = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
                .filterBounds(feature_collection) \
                .filterDate(startDate, endDate) \
                .sort('CLOUD_COVERAGE_ASSESSMENT') \
                .median()

            # # Calculate NDVI
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
            # result_list = feature_collection.map(lambda feature: 
            # ee.Feature(feature.geometry()).set({
            #     "ndvi": ndvi.reduceRegion(ee.Reducer.first(), feature.geometry()).get('ndvi')
            # })
            #    )
            
            # result = result_list.getInfo()
            # results = []
            # for o in result["features"]:
            #     res = {"ndvi": o["properties"]["ndvi"]}
            #     results.append(res)
            result_list = ndvi.sampleRegions(
            collection=feature_collection,
            scale=10,  # Adjust scale as needed
            geometries=True
                )
            #print(result_list)
            # Extract NDVI values from the result
            print(result_list)  
            results = result_list.aggregate_array('ndvi').getInfo()

            # Create a list of dictionaries with "ndvi" values
            result_dicts = [{"ndvi": ndvi} for ndvi in results]
            
            #return results
            return result_dicts

class FieldView(APIView):
    def post(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        # coordinates = json.loads(request.data["coordinates"])
        # ee_coordinates = [(float(point["lng"]), float(point["lat"])) for point in coordinates]
        # # Calculate and print the area
        # area = calculate_polygon_area(ee_coordinates)

        # request.data["area"] = area
        response = {}

        field = request.data["Field"]
        fieldSerializer = FieldSerializer(data = field)
        fieldSerializer.is_valid(raise_exception=True)
        fieldSerializer.save()
        response["Field"] = fieldSerializer.data
        response["Field"]["Field_Data"] = {}
        response["Field"]["Field_Data"]["coordinates"] = request.data["Field"]["coordinates"]


        return Response(response)
class GetStoredAvgNDVIView(APIView):
    def get(self, request, fieldID, seasonID):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
             return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)      
        field_data = Field_Data.objects.filter(field = fieldID, season = seasonID)
        response = {}
        if field_data.exists():
            print(field_data)
            response['avg_ndvi'] = field_data[0].avg_ndvi
        else:
            response['avg_ndvi'] = None
        return JsonResponse(response, safe=False)
        

class GetPointsNDVIView(APIView):
    def get(self, request):
        # token = request.COOKIES.get('jwt')

        # if not token:
        #     return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        # try:
        #     payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        # except jwt.ExpiredSignatureError:
        #      return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400) 
        # fieldID = request.data["fieldId"]
        # seasonID = request.data["seasonId"]
        # dateStr = request.data["date"]     
        # givenDate = (datetime.strptime(dateStr, '%Y-%m-%d')).date()
        # field_data = Field_Data.objects.filter(field = fieldID, season = seasonID)
        
        # response = {}
        # points_Ndvi = []
        # if field_data.exists():
        #     field_grid = Field_Grid.objects.filter(field_data =field_data[0].id )
        #     for obj in field_grid:
        #         lat_lng = obj.lat_lng
        #         point = lat_lng.replace("'", "\"")
        #         point = json.loads(point)
        #         ndvi = calculate_point_ndvi(point=point, startDate=str(givenDate-timedelta(days=1)), endDate=str(givenDate+timedelta(days=1)))
        #         points_Ndvi.append({"lat_lng": lat_lng, "ndvi": ndvi})
        #     response["Field_Grid"] = points_Ndvi
        # else:
        #     response['Error'] = "Invalid Field id or Season id"
        # return JsonResponse(response, safe=False)
        


        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
             return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400) 
        fieldID = request.data["fieldId"]
        seasonID = request.data["seasonId"]
        dateStr = request.data["date"]     
        givenDate = (datetime.strptime(dateStr, '%Y-%m-%d')).date()
        field_data = Field_Data.objects.filter(field = fieldID, season = seasonID)
        print("asdfas", field_data[0].id)
        response = {}
        points_Ndvi = []
        if field_data.exists():
            field_grid = Field_Grid.objects.filter(field_data =field_data[0].id )
            batch_points = []
            for obj in field_grid:
                lat_lng = obj.lat_lng
                point = lat_lng.replace("'", "\"")
                point = json.loads(point)
                batch_points.append(ee.Geometry.Point(float(point['lng']), float(point['lat'])))
                #ndvi = calculate_point_ndvi(point=point, startDate=str(givenDate-timedelta(days=1)), endDate=str(givenDate+timedelta(days=1)))
                #points_Ndvi.append({"lat_lng": lat_lng, "ndvi": ndvi})
            feature_collection = ee.FeatureCollection(batch_points)
           # feature_collection = ee.FeatureCollection(point_collection)
            print("Feature Colection: ", feature_collection.size())
            image = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
                .filterDate(str(givenDate-timedelta(days=1)), str(givenDate+timedelta(days=1))  ) \
                .filterBounds(feature_collection) \
                .sort('CLOUD_COVERAGE_ASSESSMENT') \
                .median()
            
            #print(image)
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
    #         result_list = []
    #         for point in feature_collection.getInfo()['features']:
    #             geometry = point['geometry']
    #             coords = geometry['coordinates']
    #             lon, lat = coords[0], coords[1]

    #             # Create a point geometry for the current feature
    #             point_geom = ee.Geometry.Point(lon, lat)

    #             # Extract the NDVI value for the current point
    #             ndvi_value = ndvi.sample(point_geom).first().get('ndvi')

    #             result_list.append({
    #             "lat_lng": f"{{'lat': '{lat}', 'lng': '{lon}'}}",
    #             "ndvi": ndvi_value.getInfo()
    # })
            result_list = ndvi.sampleRegions(
                collection=feature_collection,
                scale=10,  # Adjust scale as needed
                geometries=True
            )
            # Print the resulting dictionary
           # print("NDVI dictionary:", ndvi_dict)
            # # band_names = image.bandNames()
            # # Print the band names
            # # print("Band names:", band_names.getInfo())
            # scale = 10  # Adjust the scale based on your needs
            # crs = 'EPSG:4326'  # WGS84
            # ndvi_collection = ndvi.reduceRegions(feature_collection, ee.Reducer.mean(), scale=scale, crs=crs)
            # #print("sdfsdf:" ,ndvi_collection)
            # features = ndvi_collection.getInfo()['features']
            # #print("ssssssssss", features)
            # for i, obj in enumerate(field_grid):
            #     lat_lng = obj.lat_lng
            #     ndvi = features[i]['properties']['ndvi']
            #     points_Ndvi.append({"lat_lng": lat_lng, "ndvi": ndvi})
            print("Result list:", result_list.getInfo())
            result = result_list.getInfo()
            #print(result)
            results = []
            for o in result["features"]:
                lat = o["geometry"]["coordinates"][1]
                lng = o["geometry"]["coordinates"][0]
                s = f"{{'lat': '{lat}', 'lng': '{lng}'}}"
                res = {"lat_lng": s, "ndvi": o["properties"]["ndvi"]}
                results.append(res)

            response["Field_Grid"] = results
        else:
            response['Error'] = "Invalid Field id or Season id"
        return JsonResponse(response, safe=False)

class FieldStatsView(APIView): 
    def post(self, request, fieldId):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
             return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)      
        
        response = {}
        fieldData = request.data["Field_Data"]
        fieldData["field"] = fieldId
        

        coordinates = json.loads(fieldData["coordinates"])
        avgNDVI = calculate_avg_ndvi(coordinates=coordinates, startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1)))
        fieldData["avg_ndvi"] = avgNDVI

        ee_coordinates = [(float(point["lng"]), float(point["lat"])) for point in coordinates]
        # Calculate and print the area
        area = calculate_polygon_area(ee_coordinates)
        fieldData["area"] = area
        
        fieldDataSerializer = FieldDataSerializer(data = fieldData)
        fieldDataSerializer.is_valid(raise_exception=True)
        fieldDataSerializer.save()
        response["Field_Data"] = fieldDataSerializer.data


        field_Grid = request.data["Field_Grid"]
        points = json.loads(field_Grid["lat_lng"])
        ndvi_results = calculate_point_ndvi2(points=points, startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1))) 
        
       # print(ndvi_results)
        gridResponse = []
        for point, ndvi in zip(points, ndvi_results):
            
            data = {"field_data" : response['Field_Data']['id'],
                    "lat_lng": str(point),
                    "ndvi": ndvi["ndvi"]}
            fieldGridSerializer = FieldGridSerializer(data = data)
            fieldGridSerializer.is_valid(raise_exception=True)
            fieldGridSerializer.save()
            gridResponse.append(fieldGridSerializer.data)
        
        response["Field_Data"]["Field_Grid"] = gridResponse


        return Response(response)



        


class GetFields(APIView):
    def get(self, request, farmid, seasonid):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
         # Retrieve the farm and season instances
        farm = get_object_or_404(Farm, id=farmid)
        season = get_object_or_404(Season, id=seasonid, farm=farm)

        # Retrieve all fields for the given farm and season
        fields = Field.objects.filter(farm=farm).select_related('farm')


        # Initialize an empty list to store the nested data
        fields_data = []
        count = -1
        # Iterate over each field and retrieve associated data
        for field in fields:
            count = count + 1
            field_data = {
                'id': field.id,
                'name': field.name,
                'farm': field.farm.id,
                
            }

            # Retrieve field data for the given season
            field_data_objects = Field_Data.objects.filter(field=field.id, season=season)
            
            # Iterate over each field data and retrieve associated grid data
            
            for field_data_obj in field_data_objects:
                
                field_data_entry = {
                    'id': field_data_obj.id,
                    'season': field_data_obj.season.id,
                    'field': field_data_obj.field.id,
                    'coordinates': field_data_obj.coordinates,
                    'crop_name': field_data_obj.crop_name,
                    'avg_ndvi': field_data_obj.avg_ndvi,
                    'area': field_data_obj.area,
                    'created_at': field_data_obj.created_at.strftime('%Y-%m-%d'),
                    'Field_Grid': [],
                }

                # Retrieve field grid data
                field_grid_objects = Field_Grid.objects.filter(field_data=field_data_obj)

                # Iterate over each field grid and add to the field_data_entry
                for field_grid_obj in field_grid_objects:
                    field_grid_entry = {
                        'lat_lng': field_grid_obj.lat_lng,
                        'ndvi': field_grid_obj.ndvi,
                    }
                    field_data_entry['Field_Grid'].append(field_grid_entry)

                # Append the field_data_entry to the field_data list
                field_data['Field_Data'] = field_data_entry
            
            # Append the field_data to the main listq
            if field_data_objects.exists():
                fields_data.append(field_data)

            # Create a JSON response
        response_data = {'fields_data': fields_data}
        return JsonResponse(response_data, safe=False)


class DeleteFieldView(APIView):   
    def delete(self, request, fieldId, seasonId):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        field_data = get_object_or_404(Field_Data, field=fieldId, season = seasonId)
        field_data.delete()
        field_data1 = Field_Data.objects.filter(field=fieldId)
        print(field_data1)
        if not field_data1.exists():
            field = get_object_or_404(Field, pk = fieldId)
            field.delete()
           
        return Response(status=200)


class PatchFieldView(APIView): 
    def patch(self, request, fieldId, seasonId):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        # if "name" in request.data["Field"]:
        response = {}
        field = get_object_or_404(Field, pk=fieldId)
        serializer = FieldSerializer(field, data=request.data["Field"], partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response["Field"] = serializer.data
        if "coordinates" in request.data["Field_Data"]:
            coordinates = json.loads(request.data["Field_Data"]["coordinates"])
            avgNDVI = calculate_avg_ndvi(coordinates,startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1)))
            request.data["Field_Data"]["avg_ndvi"] = avgNDVI

            ee_coordinates = [(float(point["lng"]), float(point["lat"])) for point in coordinates]
            # Calculate and print the area
            area = calculate_polygon_area(ee_coordinates)
            request.data["Field_Data"]["area"] = area
        field_data = get_object_or_404(Field_Data, field=fieldId, season = seasonId)
        
        fieldDataSerializer = FieldDataSerializer(field_data, data=request.data["Field_Data"], partial=True)
        fieldDataSerializer.is_valid(raise_exception=True)
        fieldDataSerializer.save()
        response["Field_Data"] = fieldDataSerializer.data

        if "lat_lng" in request.data["Field_Grid"]:
            Field_Grid.objects.filter(field_data=field_data.id).delete()
            points = json.loads(request.data["Field_Grid"]["lat_lng"])
            ndvi_results = [calculate_point_ndvi(point,startDate=str(date.today()-timedelta(days=5)), endDate=str(date.today()+timedelta(days=1))) for point in points]
            gridResponse = []
            for point, ndvi in zip(points, ndvi_results):
                data = {"field_data" : field_data.id,
                        "lat_lng": str(point),
                        "ndvi": ndvi}
                fieldGridSerializer = FieldGridSerializer(data = data)
                fieldGridSerializer.is_valid(raise_exception=True)
                fieldGridSerializer.save()
                gridResponse.append(fieldGridSerializer.data)
            response["Field_Grid"] = gridResponse
                # if "coordinates" in request.data:
        #     coordinates = json.loads(request.data["coordinates"])
        #     ee_coordinates = [(float(point["lng"]), float(point["lat"])) for point in coordinates]
        #     # Calculate and print the area
        #     area = calculate_polygon_area(ee_coordinates)
        #     request.data["area"] = area
        # field = get_object_or_404(Field, pk=fieldId)
        # serializer = FieldSerializer(field, data=request.data, partial=True)
        # serializer.is_valid(raise_exception=True)
        # serializer.save()
        return Response(response)


class AvgNDVI(APIView):
    def get(self, request, id):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        
        queryset = Field.objects.filter(farm=id)
        final_response = []
        for field in queryset:
            coordinates = field.coordinates
            coordinates = json.loads(coordinates)
            for coord in coordinates:
                coord['lat'] = float(coord['lat'])
                coord['lng'] = float(coord['lng'])
            
            polygon_coordinates = [[coord['lng'], coord['lat']] for coord in coordinates]
            
            
            # Create a polygon geometry from the coordinates
            polygon_geometry = ee.Geometry.Polygon(polygon_coordinates)
            
            # Define Sentinel-2 image collection and filter by date
            collection = (
                ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
                .filterBounds(polygon_geometry)
                .filterDate('2023-01-01', '2023-12-31')  # Adjust date range as needed
                .sort('CLOUD_COVERAGE_ASSESSMENT')
            )

            # Calculate NDVI for the collection
            def calculate_ndvi(image):
                ndvi = image.normalizedDifference(['B8', 'B4'])
                return image.addBands(ndvi.rename('NDVI'))

            collection_with_ndvi = collection.map(calculate_ndvi)
            merged_image = collection_with_ndvi.median()
            # Calculate average NDVI for the polygon region
            average_ndvi = (
                merged_image
                .select('NDVI')
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=polygon_geometry,
                    scale=10,  # Adjust the scale as needed
                    bestEffort = True
                )
                .get('NDVI')
            )

            # Convert the result to a JSON response
            response_data = {
                'id': field.id,
                'average_ndvi': average_ndvi.getInfo(),
            }
            final_response.append(response_data)
        return Response(final_response)
    

class GridNDVI(APIView):
    def post(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        points = json.loads(request.body)
        def calculate_ndvi(point):
            # Create a Point geometry from the given coordinates
            point_geometry = ee.Geometry.Point(float(point['lng']), float(point['lat']))
             
            # Use Landsat 8 imagery for NDVI calculation (you can change this as needed)
            image = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
                .filterBounds(point_geometry) \
                .filterDate('2020-01-01', '2020-12-31') \
                .sort('CLOUD_COVERAGE_ASSESSMENT') \
                .median()

            # Calculate NDVI
            ndvi = image.normalizedDifference(['B5', 'B4'])

            # Get the NDVI value as a number
            ndvi_value = ndvi.reduceRegion(ee.Reducer.mean(), point_geometry, 10).get('nd')
            ndvi_value = ee.Number(ndvi_value).getInfo() 
            return {'coordinates': point, 'ndvi': ndvi_value}

            
            

        # Calculate NDVI for each coordinate and store the results in a new list
        ndvi_results = [calculate_ndvi(point) for point in points]

        return Response(ndvi_results)
    
def copyFields(farm_id, season_id):
        queryset = Field.objects.filter(farm=farm_id)
        for field in queryset:
            field_data_obj = Field_Data.objects.filter(field = field.id).order_by('-created_at').first()
            if field_data_obj is not None:
                field_data_dict = {
                    "field": field_data_obj.field.id,
                    "season": season_id,
                    "coordinates": field_data_obj.coordinates,
                    "area" : field_data_obj.area,
                    "avg_ndvi": field_data_obj.avg_ndvi
                    
                }
                fieldDataSerializer = FieldDataSerializer(data = field_data_dict)
                fieldDataSerializer.is_valid(raise_exception=True)
                fieldDataSerializer.save()
                field_grid_queryset = Field_Grid.objects.filter(field_data = field_data_obj.id)
                for field_grid in field_grid_queryset:
                    field_grid_dict = {
                        "field_data": fieldDataSerializer.data["id"],
                        "lat_lng": field_grid.lat_lng,
                        "ndvi": field_grid.ndvi 
                    }
                    fieldGridSerializer = FieldGridSerializer(data = field_grid_dict)
                    fieldGridSerializer.is_valid(raise_exception=True)
                    fieldGridSerializer.save()    

        # queryset = Farm.objects.filter(user=user_id)
        # for farm in queryset:
        #     queryset2 = Field.objects.filter(farm = farm.id)
        #     for field in queryset2:
        #         field_dict = {"name": field.name,
        #                       "farm": field.farm.id,
        #                       "season": season_id,
        #                         "coordinates": field.coordinates}
                
        #         serializer = FieldSerializer(data = field_dict)
        #         serializer.is_valid(raise_exception=True)
        #         serializer.save()
                

class SeasonView(APIView):        
    def post(self, request):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        data = request.data
        serializer = SeasonSerializer(data = data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if data["copy_fields"] == "True":
            copyFields(request.data["farm"], serializer.data["id"])
        #     latest_season = Season.objects.filter(user_id=data["user"]).order_by('-id').first()
        #     copyFields(data["user"], latest_season.id)



        return Response(serializer.data)
    
    
class GetSeasons(APIView):
    def get(self, request, farmId):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        
        queryset = Season.objects.filter(farm = farmId)
        serializer = SeasonSerializer(queryset, many=True)
        return Response(serializer.data)    

class SeasonDetail(APIView):
    
    def patch(self, request, id):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        season = get_object_or_404(Season, pk=id)
        serializer = SeasonSerializer(season, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    def delete(self, request, id):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        season = get_object_or_404(Season, pk=id)
        season.delete()

        Field.objects.exclude(field_data__isnull=False).delete()
        return Response(status=200)
    

class JobView(APIView):
    def post(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        response = {}

        job_data = request.data["Job"]
    
        job_serializer = JobSerializer(data = job_data)
        job_serializer.is_valid(raise_exception=True)
        job_serializer.save()
        job_id = job_serializer.data['id']

        response["Job"] = job_serializer.data

        job_inputs = request.data["Job_Input"]
        job_input_response = []
        for job_input in job_inputs:
            job_input['job'] = job_id
            job_input_serializer = JobInputSerializer(data = job_input)
            job_input_serializer.is_valid(raise_exception=True)
            job_input_serializer.save()
            job_input_response.append(job_input_serializer.data)

        response["Job_Input"] = job_input_response


        job_fields = request.data["Job_Field"]
        job_field_response = []
        for job_field in job_fields:
            job_field["job"] = job_id
            job_field_serializer = JobFieldSerializer(data = job_field)
            job_field_serializer.is_valid(raise_exception=True)
            job_field_serializer.save()
            job_field_response.append(job_field_serializer.data)

        response["Job_Field"] = job_field_response

        return Response(response)

class GetJobsView(APIView):
    def get(self, request, seasonId):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        jobs = Job.objects.filter(season=seasonId).select_related('season').prefetch_related('job_field_set', 'job_input_set')
        response = []
        for job in jobs:
            j = {
                "id": job.id,
                "season":job.season.id,
                "type":job.type,
                "name":job.name,
                "due_date": job.due_date,
                "due_time": job.due_time,
                "status": job.status,
                
                "job_input": [],
                "job_field": []
            }

            for job_input in job.job_input_set.all():
                job_i = {
                    "id": job_input.id,
                    "job": job_input.job.id,
                    "name": job_input.name,
                    "type": job_input.type,
                    "unit": job_input.unit,
                    "application_rate_per_hector": job_input.application_rate_per_hector,
                    "total": job_input.total,
                    "n1":job_input.n1,
                    "n2":job_input.n2,
                    "n3":job_input.n3,
                    "n4":job_input.n4,
                    "n5":job_input.n5,
                    "n6":job_input.n6
                }
                j["job_input"].append(job_i)
            
            for job_field in job.job_field_set.all():
                job_f = {
                    "job": job_field.job.id,
                    "field":job_field.field.id
                }
                j["job_field"].append(job_f)
            
            response.append(j)
        response_data = {'jobs_data': response}
        return JsonResponse(response_data, safe=False)


class DeletePatchJobsView(APIView):
    def delete(self, request, jobId):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        job = get_object_or_404(Job, pk=jobId)
        job.delete()
        return Response(status=200)

    def patch(self, request, jobId):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        job_inputs = Job_Input.objects.filter( job=jobId)
        job_inputs.delete()

        job_fields = Job_Field.objects.filter(job=jobId)
        job_fields.delete()
        
        response = {}
        job_data = request.data["Job"]
        job = get_object_or_404(Job, pk=jobId)
        jobSerializer = JobSerializer(job, data= job_data, partial=True)
        jobSerializer.is_valid(raise_exception=True)
        jobSerializer.save()

        response["Job"] = jobSerializer.data

        job_inputs = request.data["Job_Input"]
        job_input_response = []
        for job_input in job_inputs:
            job_input['job'] = jobId
            job_input_serializer = JobInputSerializer(data = job_input)
            job_input_serializer.is_valid(raise_exception=True)
            job_input_serializer.save()
            job_input_response.append(job_input_serializer.data)

        response["Job_Input"] = job_input_response


        job_fields = request.data["Job_Field"]
        job_field_response = []
        for job_field in job_fields:
            job_field["job"] = jobId
            job_field_serializer = JobFieldSerializer(data = job_field)
            job_field_serializer.is_valid(raise_exception=True)
            job_field_serializer.save()
            job_field_response.append(job_field_serializer.data)

        response["Job_Field"] = job_field_response
        response_data = {'jobs_data': response}
        return JsonResponse(response_data, safe=False)
        
def convert_Into_Numpy_Format(data_list):
    array = np.array([(
    d['B1'],
    d['B11'],
    d['B12'],
    d['B2'],
    d['B3'],
    d['B4'],
    d['B5'],
    d['B6'],
    d['B7'],
    d['B8'],
    d['B8A'],
    d['B9'],
    d['NDVI'],
    )for d in data_list])

    return array

def convert_Into_Numpy_Format2(data_list):
    array = []

    for i in range(0, len(data_list.getInfo()['features'])):
        temp = []
        temp.append(data_list.getInfo()['features'][i]['properties'])
        array.append(convert_Into_Numpy_Format(temp))
    return  array


class ClassificationView(APIView):
    def post(self, request):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        
        
        S2 = ee.ImageCollection("COPERNICUS/S2")
        
        def addNDVI_S2(img):
            ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return img.addBands(ndvi)
        coordinates = request.data["coordinates"]
        coordinates = json.loads(coordinates)
        for coord in coordinates:
            coord['lat'] = float(coord['lat'])
            coord['lng'] = float(coord['lng'])

        polygon_coordinates = [[coord['lng'], coord['lat']] for coord in coordinates]
        # Create a polygon geometry from the coordinates

        polygon_geometry = ee.Geometry.Polygon(polygon_coordinates)
        filtered = S2.filterBounds(polygon_geometry)

        sorted_collection = filtered.sort('system:time_start', False).map(addNDVI_S2)
        most_recent_image = sorted_collection.first()
        features = most_recent_image.sampleRegions(collection=polygon_geometry,scale=30)

        indices = features.getInfo()
        dictionary = {}

        dictionary['B1'] = indices.get('B1')
        dictionary['B11'] = indices.get('B11')
        dictionary['B12'] = indices.get('B12')
        dictionary['B2'] = indices.get('B2')
        dictionary['B3'] = indices.get('B3')
        dictionary['B4'] = indices.get('B4')
        dictionary['B5'] = indices.get('B5')
        dictionary['B6'] = indices.get('B6')
        dictionary['B7'] = indices.get('B7')
        dictionary['B8'] = indices.get('B8')
        dictionary['B8A'] = indices.get('B8A')
        dictionary['B9'] = indices.get('B9')
        dictionary['NDVI'] = indices.get('NDVI')

        input_data=[]
        input_data.append(dictionary)
        input_array = convert_Into_Numpy_Format2(features)

        iclassifier = joblib.load('cotton22_rf.joblib')
        predictions = iclassifier.predict(np.vstack(input_array))

        # print(predictions)
        element_counts = defaultdict(int)

        # Count occurrences of elements in the array
        for element in predictions:
            element_counts[element] += 1

        # Convert the defaultdict to a regular dictionary if needed
        element_counts = dict(element_counts)

        def get_most_common_label(element_counts):
            labels = {0: "No Crop", 1: "Cotton", 2: "Other Crop"}

            # Find the element with the highest count
            most_common_element = max(element_counts, key=element_counts.get)

            # Get the label for the most common element
            most_common_label = labels.get(most_common_element, "Unknown")

            return most_common_label

        finalPrediction = get_most_common_label(element_counts)
       
        return JsonResponse({"prediction": finalPrediction})



class CropRotationView(APIView):
    def get(self, request, farmId):
        token = request.COOKIES.get('jwt')
        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)
        fields_with_crop_rotation = Field.objects.filter(farm=farmId).select_related('farm')
        fields_with_crop_rotation = fields_with_crop_rotation.prefetch_related(
            Prefetch(
                'field_data_set',
                queryset=Field_Data.objects.select_related('season').order_by('-season__start_date'),
                to_attr='crop_rotation'
            )
        )
        response = {"data": []}
        response["data"] = [
            {
                'fieldId': field.id,
                'fieldName': field.name,
                
                'cropRotation': [
                    {
                        'season': {
                            'id': crop.season.id,
                            'name': crop.season.name,
                            'start_date': crop.season.start_date.strftime('%Y-%m-%d'),
                            'end_date': crop.season.end_date.strftime('%Y-%m-%d'),
                        },
                        'cropName': crop.crop_name,
                        
                    }
                    for crop in field.crop_rotation
                ],
            }
            for field in fields_with_crop_rotation
        ]
        return JsonResponse(response)
