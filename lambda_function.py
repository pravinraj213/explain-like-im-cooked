import json
import boto3
import os
from botocore.exceptions import ClientError

# Region configuration (defaulting to ap-south-1 Mumbai)
AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')

# Initialize Bedrock Runtime client
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# In ap-south-1 and APAC regions, Nova models require the regional inference profile
DEFAULT_MODEL = 'apac.amazon.nova-lite-v1:0' if AWS_REGION.startswith('ap-') else 'amazon.nova-lite-v1:0'
MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', DEFAULT_MODEL)
MAX_TOKENS = 2048
TEMPERATURE = 0.5


def build_system_prompt(panic_level):
    """
    Build the system prompt based on panic level.
    
    Args:
        panic_level: Integer from 0-100 indicating urgency
        
    Returns:
        String containing the system prompt
    """
    if panic_level >= 71:
        return """You are an emergency technical diagnostics agent helping an engineer during a production or build incident.
Your response MUST strictly adhere to this exact format:

### THE FIX
```
[Exact copy-paste fix - 1 command, config snippet, or code change]
```

### WHAT ACTUALLY HAPPENED
[ONE direct sentence explaining the technical root cause in plain English with zero jargon]

### SANITY CHECK
[ONE brief reassuring sentence on next verification step]

Rules:
- Zero introductory or concluding fluff.
- No emojis anywhere in the output.
- The fix must directly resolve the provided error."""
    elif panic_level >= 31:
        return """You are a senior technical advisor assisting an engineer.
Your response MUST follow this format:

### THE FIX
```
[Direct command, config, or code change to resolve the issue]
```

### WHAT ACTUALLY HAPPENED
[A concise explanation including a simple, intuitive real-world analogy]

### SANITY CHECK
[One reassuring sentence and a suggested check]

Rules:
- No emojis anywhere in the output.
- Keep explanations crisp, practical, and grounded."""
    else:
        return """You are a patient staff software engineer explaining an error conceptually.
Your response MUST follow this format:

### THE FIX
```
[The correct code or configuration]
```

### WHAT ACTUALLY HAPPENED
[A clear, thorough explanation of the underlying system architecture or mechanism that failed]

### SANITY CHECK
[Key concept to remember to prevent this in the future]

Rules:
- No emojis anywhere in the output.
- Educational, clear, and technically precise."""


def lambda_handler(event, context):
    """
    AWS Lambda handler for Explain Like I'm Cooked.
    """
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        'Content-Type': 'application/json'
    }

    # Determine HTTP Method (works for REST API and HTTP API v2)
    method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    if method in ['GET', 'HEAD']:
        raw_path = event.get('rawPath', '') or event.get('path', '')
        if raw_path == '/rescue':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'status': 'online',
                    'service': "Explain Like I'm Cooked",
                    'model': 'Amazon Bedrock Nova Lite (apac.amazon.nova-lite-v1:0)',
                    'message': 'API is active. Send POST /rescue with JSON: {"error_text": "...", "panic_level": 85}'
                })
            }
        
        user_agent = event.get('headers', {}).get('user-agent', 'Unknown')
        print(f"[VISIT] Path: {raw_path or '/'} | Agent: {user_agent[:50]}")

        # Serve the single-page web app
        try:
            with open(os.path.join(os.path.dirname(__file__), 'index.html'), 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            html_content = f"<!DOCTYPE html><html><body><h1>Explain Like I'm Cooked</h1><p>Error loading UI: {e}</p></body></html>"

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': html_content
        }

    try:
        # Parse body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        error_text = body.get('error_text', '').strip()
        panic_level = body.get('panic_level', 85)

        if not error_text:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'error_text is required and cannot be empty'})
            }

        try:
            panic_level = max(0, min(100, int(panic_level)))
        except (ValueError, TypeError):
            panic_level = 85

        clean_snippet = error_text.replace('\n', ' ')[:75]
        print(f"[DIAGNOSE_REQUEST] Urgency: {panic_level}% | Input: {clean_snippet}...")

        system_prompt = build_system_prompt(panic_level)
        user_message = f"Error log / stack trace:\n\n{error_text}\n\nUrgency level: {panic_level}/100"

        # Attempt Bedrock Converse API invocation
        try:
            response = bedrock_runtime.converse(
                modelId=MODEL_ID,
                messages=[
                    {
                        'role': 'user',
                        'content': [{'text': user_message}]
                    }
                ],
                system=[{'text': system_prompt}],
                inferenceConfig={
                    'maxTokens': MAX_TOKENS,
                    'temperature': TEMPERATURE
                }
            )

            output_message = response['output']['message']
            explanation = output_message['content'][0]['text']

            bedrock_latency = response.get('metrics', {}).get('latencyMs', 0)
            total_toks = response.get('usage', {}).get('totalTokens', 0)
            print(f"[DIAGNOSE_SUCCESS] Latency: {bedrock_latency}ms | Tokens: {total_toks}")

            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'explanation': explanation,
                    'model_id': MODEL_ID,
                    'region': AWS_REGION,
                    'panic_level': panic_level,
                    'usage': response.get('usage', {})
                })
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"Bedrock ClientError: {error_code} - {error_msg}")

            # If model ID fails due to inference profile requirement, retry with regional prefix
            if 'inference profile' in error_msg.lower() and not MODEL_ID.startswith('apac.'):
                fallback_model = f"apac.{MODEL_ID}"
                try:
                    retry_response = bedrock_runtime.converse(
                        modelId=fallback_model,
                        messages=[{'role': 'user', 'content': [{'text': user_message}]}],
                        system=[{'text': system_prompt}],
                        inferenceConfig={'maxTokens': MAX_TOKENS, 'temperature': TEMPERATURE}
                    )
                    explanation = retry_response['output']['message']['content'][0]['text']
                    return {
                        'statusCode': 200,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'explanation': explanation,
                            'model_id': fallback_model,
                            'region': AWS_REGION,
                            'panic_level': panic_level
                        })
                    }
                except Exception as retry_err:
                    print(f"Retry failed: {retry_err}")

            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': f"Bedrock invocation error: {error_code}",
                    'details': error_msg
                })
            }

    except json.JSONDecodeError as e:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }


if __name__ == '__main__':
    test_event = {
        'body': json.dumps({
            'error_text': 'AccessDeniedException: User: arn:aws:iam::123:user/dev is not authorized to perform: s3:GetObject',
            'panic_level': 85
        })
    }
    res = lambda_handler(test_event, None)
    print(json.dumps(json.loads(res['body']), indent=2))
