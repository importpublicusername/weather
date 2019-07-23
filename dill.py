#system libraries
import pickle
import boto3

#third party
#from logzero import logger
#from loguru import logger

def writepickle(data, filename):
    s3 = boto3.client('s3')
    serializedListObject = pickle.dumps(data)
    s3.put_object(Bucket='weather-lambda-myapp',Key=filename,Body=serializedListObject)

def readpickle(filename):
    try:
        s3 = boto3.client('s3')
        object = s3.get_object(Bucket='weather-lambda-myapp',Key=filename)
        serializedObject = object['Body'].read()
        myList = pickle.loads(serializedObject)
        return myList
    except:
        return None
