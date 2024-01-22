# ChatGPT action projects

This repository will provide detailed guides for building a variety of ChatGPT actions built on Cloud Services.

ChatGPT actions let LLMs call APIs automatically based on API description to answer user queries or complete tasks from users.

## Example 1: Connect ChatGPT action with Pokemon APIs on AWS

<img src="./pic/pikachu.png" width="100" />

### Overview

This tutorial goes through step by step how to integrate [ChatGPT actions](https://platform.openai.com/docs/actions/introduction) with APIs deployed on AWS. We will make ChatGPT gain knowledge about [Pokemon](https://www.pokemon.com/us), using information from a public API [pokeapi.co](https://pokeapi.co).

The **ChatGPT prompt** this example will use is:
```text
Create an action where users can request information about a specific Pokémon. When a user inputs the name of a Pokémon, your action should utilize the designated API to retrieve details about that Pokémon. Currently, the API response includes only the abilities of the Pokémon. Ensure that your action captures this information accurately and presents it back to the user. Keep in mind that the information provided to users is limited to what is available from the API's response.
```

<img src="./pic/pokeapi_example.png" width="400" />

The flow is:
1. User submit a query
2. LLM invokes the Cloud Pokemon API that we will create on AWS
3. AWS API gateway receives the call, and forward it to Lambda function to process
4. The Lambda function calls [pokeapi.co](https://pokeapi.co)
5. LLM receives the information in API response, and use this knowledge in answer generation

We will be able to provide rich information about Pokemons by querying pokeapi.co. For demo purpose, we limit the scope to:
- Input of the API is the Pokemon, for example, `pikachu` or `ditto`.
- The API response only returns the `abilities` attribute. Therefore the LLM will only provide Pokemon's abilities in its answer.

### Prerequisite

- You need to have [ChatGPT plus](https://openai.com/blog/chatgpt-plus) subscription to be able to use ChatGPT actions.
- You need to have an AWS account.
- This guide uses [AWS CLI](https://aws.amazon.com/cli/). Follow [the AWS doc](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) to install and setup the CLI.

### AWS Lambda function

This example uses [Lambda functions](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) as the backend of the API service. The folder [aws/lambda/pokeapi_fn](./aws/lambda/pokeapi_fn/) contains the source files to create and deploy the function.

The prerequiste is a [Lambda execution role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html), skip this step if you already have one:

```bash
aws iam create-role \
    --role-name lambda-ex \
    --assume-role-policy-document '{"Version": "2012-10-17","Statement": [{ "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}'
```

The output contains the role ARN, for example, "arn:aws:iam::<account-id>:role/lambda-ex". We use a place holder var `ROLE_ARN` to represent it.

Go to the folder of Python files, [create a Zip file](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html), and [create the Lambda function](https://docs.aws.amazon.com/cli/latest/reference/lambda/create-function.html):

```bash
cd aws/lambda/pokeapi_fn
zip pokeapi_fn.zip lambda_function.py

aws lambda create-function \
    --function-name pokeapi_fn \
    --runtime python3.12 \
    --zip-file fileb://pokeapi_fn.zip \
    --handler lambda_function.lambda_handler \
    --role "${ROLE_ARN}"
```

Invoke the function to verify it works. Its input `queryStringParameters` will be populated by the AWS API gateway.

```bash
aws lambda invoke \
    --function-name pokeapi_fn \
    --cli-binary-format raw-in-base64-out \
    --payload '{"queryStringParameters": {"name": "pikachu"}}' \
    response.json

cat response.json
# Output:
# {"statusCode": 200, "body": "{\"pokemon\": {\"name\": \"pikachu\",
# \"abilities\": [\"static\", \"lightning-rod\"]}}"}
```

### AWS API gateway

We use [API Gateway](https://aws.amazon.com/api-gateway/) to expose the Lambda function to the public with administration control (API key). We will give the API key to ChatGPT when invoking our API.

# Create API and resources

Follow the [AWS guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-api-as-simple-proxy-for-lambda.html) to create the Pokemon API:

```bash
# Create a REST API
aws apigateway create-rest-api \
    --name 'Pokemon APIs' \
    --description 'Simple APIs wrapping https://pokeapi.co' \
    --region us-east-1 \
    --endpoint-configuration 'types=REGIONAL'

# Paste response['id'] here:
export API_ID='placeholder'
# Paste response['rootResourceId'] here:
export ROOT_RESOURCE_ID='placeholder'  

# Create a API resource `/pokemons` under the root `/`
aws apigateway create-resource \
    --rest-api-id ${API_ID} \
    --parent-id ${ROOT_RESOURCE_ID} \
    --path-part 'pokemons'

# Paste response['id'] here:
export RESOURCE_ID='a11ncw'

# Create a method so API gateway will call lambda
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${RESOURCE_ID} \
    --http-method ANY \
    --authorization-type "NONE" \
    --api-key-required

aws apigateway put-method-response \
    --rest-api-id ${API_ID} \
    --resource-id ${RESOURCE_ID} \
    --http-method ANY \
    --status-code 200

# Must use AWS_PROXY, for API gateway to send GET query parameter to lambda
# Replace `uri` with the Lambda function you just created
aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${RESOURCE_ID} \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri 'arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123412341234:function:function_name/invocations' \
    --content-handling 'CONVERT_TO_TEXT'

# Create a `test` deployment to test the API
aws apigateway create-deployment \
    --rest-api-id ${API_ID} \
    --stage-name 'test'
```

## API key and usage plan

We want to restrict the access to our API. This can be achieved by creating an [API key](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-setup-api-key-with-console.html). AWS requires the API key to link to a [usage plan](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html). And the usage plan needs to be linked with the `test` deployment we just created.

Following the steps to setup all of them:

```bash
# Create an API key
aws apigateway create-api-key \
    --name 'Pokemon API Key' \
    --description 'Used for Pokemon API' \
    --enabled

# Paste response['id'] here:
export API_KEY_ID='placeholder'
# Paste response['value'] here:
export API_KEY='placeholder'  

# Create a usage plan and link with the stage `test`
aws apigateway create-usage-plan \
    --name "Pokemon API usage plan" \
    --description "Pokemon API usage plan" \
    --throttle 'burstLimit=10,rateLimit=5' \
    --quota 'limit=500,offset=0,period=MONTH' \
    --api-stages "[{\"apiId\":\"${API_ID}\", \"stage\":\"test\"}]"

# Paste response['id'] here:
export USAGE_PLAN_ID='placeholder'  

# Add the API key to the usage plan
aws apigateway create-usage-plan-key \
    --usage-plan-id ${USAGE_PLAN_ID} \
    --key-type 'API_KEY' \
    --key-id ${API_KEY_ID}

# Re-deploy the API to apply the change
aws apigateway create-deployment \
    --rest-api-id ${API_ID} \
    --stage-name 'test'
```

### Validate API

After the steps being completed, we are able to test the Pokemon API from our local machine:

```bash
curl -X GET \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    "https://${API_ID}.execute-api.us-east-1.amazonaws.com/test/pokemons"
```

### Create ChatGPT

Create a new GPT and fill in the prompt in [the overview](#overview):

<img src="./pic/chatgpt_prompt.png" width="400" />

Now let's configure **ChatGPT actions**.

#### Authentication
- Use `API key`, fill your API key above (`${API_KEY}`).
- Select `Custom` for `Auth type`. Fill `Custom Header Name` with `x-api-key` (AWS uses it for API keys).

#### API schema

ChatGPT how the capabilities of APIs and how to invoke them from API schema defined in the [OpenAPI](https://www.openapis.org/) format. Fill in the schema below that described our Pokemon API (don't forget to replace `url` with your API Gateway URL):

```yaml
openapi: 3.1.0
info:
  title: Pokemon API
  description: Return the details of Pokemon
  version: 1.0.0
servers:
  - url: https://api-id.execute-api.us-east-1.amazonaws.com
paths:
  /test/pokemons:
    get:
      description: Return the details of a Pokemon specified by the name
      operationId: get_pokemons
      parameters:
        - name: name
          schema:
            type: string
          in: query
          required: true
          description: Name of a Pokemaon
```

#### Publish GPT and chat about Pokemon!


