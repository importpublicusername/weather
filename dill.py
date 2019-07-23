#system libraries
import pickle

def writepickle(data, filename, mode):
    if mode == 'lambda':
        import boto3
        s3 = boto3.client('s3')
        serializedListObject = pickle.dumps(data)
        s3.put_object(Bucket='weather-lambda-myapp',Key=filename,Body=serializedListObject)
    else:
        #local
        with open(filename, 'wb') as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

def readpickle(filename, mode):
    if mode == 'lambda':
        import boto3
        try:
            s3 = boto3.client('s3')
            object = s3.get_object(Bucket='weather-lambda-myapp',Key=filename)
            serializedObject = object['Body'].read()
            myList = pickle.loads(serializedObject)
            return myList
        except:
            return None
    else:
        #local
        try:
            with open(filename, 'rb') as f:
                # The protocol version used is detected automatically, so we do not
                # have to specify it.
                data = pickle.load(f)
            return data
        except:
            #logger.debug(f'file {filename} does not exist')
            return None
