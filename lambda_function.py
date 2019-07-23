import accu
#import dill

def lambda_handler(event, context):
    accu.main()
    #state = dill.readpickle('state.pickle')
    #print(state)
    #dill.writepickle(['new data'], 'state.pickle')
