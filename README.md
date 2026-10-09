# Explain Like I'm Cooked — The 2 AM Panic Agent

A serverless developer diagnostics agent built for the AWS Builder Center Weekend Challenge (`#agents`). It delivers noise-free, emergency solutions for late-night compiler crashes, AWS IAM access denials, and deployment failures using Amazon Bedrock Nova Lite.

- **Live Web App**: [https://qmyzc9gsme.execute-api.ap-south-1.amazonaws.com/](https://qmyzc9gsme.execute-api.ap-south-1.amazonaws.com/)
- **GitHub Repository**: [https://github.com/pravinraj213/explain-like-im-cooked](https://github.com/pravinraj213/explain-like-im-cooked)
- **API Endpoint**: `https://qmyzc9gsme.execute-api.ap-south-1.amazonaws.com/rescue`

---

## Architecture Overview

```
[ Developer in Browser ] 
        │
        ▼ (HTTPS)
[ Frontend: index.html (Single-page, CDN Tailwind, Vanilla JS) ]
        │
        ▼ (POST /rescue)
[ Amazon API Gateway (HTTP API with 5 req/s rate-limiting) ]
        │
        ▼
[ AWS Lambda (Python 3.12, ap-south-1) ]
        │
        ▼ (Converse API)
[ Amazon Bedrock (apac.amazon.nova-lite-v1:0) ]
```

---

## File Structure

```
weekly_challenge/
├── index.html            # Clean, mobile-responsive dark terminal frontend
├── lambda_function.py    # Python 3.12 Bedrock Converse API handler
├── iam-policy.json       # Least-privilege IAM policy for Bedrock & CloudWatch
├── trust-policy.json     # Lambda assume role trust document
├── setup.sh              # 1-command IAM role creation & Lambda deploy script
├── requirements.txt      # Python dependencies (boto3)
└── README.md             # This document
```

---

## Quick Deployment

### 1. Prerequisites
- AWS CLI configured with credentials (`aws configure`)
- Active model access to Amazon Nova Lite in Bedrock

### 2. Deploy Lambda & IAM
Run the automated deployment script:
```bash
./setup.sh
```

### 3. Setup API Gateway (HTTP API)
1. In the AWS Console, open **API Gateway** -> **Create API** -> **HTTP API**.
2. Add an integration pointing to the Lambda function `explain-like-im-cooked`.
3. Create route: `POST /rescue`.
4. Under **Stages** -> `$default`:
   - Enable Throttling: Rate = 5 req/sec, Burst = 10.
5. Configure CORS:
   - Allow Origins: `*` (or your domain e.g. `https://cooked.pravinraj.me`)
   - Allow Methods: `POST, OPTIONS`
   - Allow Headers: `Content-Type`
6. Copy the Invoke URL into `index.html` (`window.EXPLAIN_API_ENDPOINT`).

---

## The Delightful Detail: The Urgency Slider

Instead of conversational small-talk, the UI features an Urgency Slider (0–100%):
- **0–30% (Calm):** Concept-first architectural explanation.
- **31–70% (Pressured):** Fast fix accompanied by an intuitive analogy.
- **71–100% (Critical):** Immediate 1-line copy-paste fix only, with zero preamble.
