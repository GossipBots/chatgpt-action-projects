import json
import urllib3

def lambda_handler(event, context):
    http = urllib3.PoolManager(cert_reqs='CERT_NONE')

    if 'queryStringParameters' not in event or 'name' not in event['queryStringParameters']:
        return {
            'statusCode': 400,
            'body': f'Invalid input: {event}'
        }

    name = event['queryStringParameters']['name']
    response = http.request('GET', 
        f'https://pokeapi.co/api/v2/pokemon/{name}')
    data = json.loads(response.data)
    
    abilities = [v['ability']['name'] for v in data['abilities']]
    pokemon = {
        'pokemon': {
            'name': name,
            'abilities': abilities
        }
        
    }
    return {
        'statusCode': 200,
        'body': json.dumps(pokemon)
    }
