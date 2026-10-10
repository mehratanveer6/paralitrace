# Deploying ParaliTrace on AWS

One Amazon EC2 instance serves the app, refreshes live NASA fires every hour, and calls Amazon Bedrock
(Amazon Nova) for the assistant through its IAM role. Everything installs from `ec2-user-data.sh`;
there is nothing to SSH in and run.

## 1. Check Bedrock works on the account (2 minutes)

1. AWS console, region **US East (N. Virginia) us-east-1** (top right).
2. Open **Amazon Bedrock -> Playgrounds -> Chat / Text**, pick **Amazon Nova Pro**, send "hello".
   An answer means Bedrock is ready (Amazon Nova needs no approval form). It also counts towards the
   Free Tier credit activities. If it says access is not allowed, the app falls back to Gemini when
   `GEMINI_API_KEY` is filled in the launch script.

## 2. Create a role the instance can use

1. **IAM -> Roles -> Create role**.
2. Trusted entity: **AWS service**, use case **EC2**. Next.
3. Attach the policy **AmazonBedrockFullAccess**. Next.
4. Name it `paralitrace-ec2`. Create.

## 3. Launch the instance

1. **EC2 -> Launch instance** (any region; Mumbai ap-south-1 is closest to India).
2. Name `paralitrace`. Image: **Ubuntu Server 24.04 LTS**. Type: **t3.micro** (free tier eligible).
3. Key pair: **Proceed without a key pair** (EC2 Instance Connect still works in the browser).
4. Network settings: tick **Allow HTTP traffic from the internet**.
5. **Advanced details**:
   - IAM instance profile: `paralitrace-ec2`.
   - User data: paste the whole of `ec2-user-data.sh` (optionally fill the keys at its top).
6. **Launch instance**.

## 4. Open it

Wait about 10 minutes for the install. Copy the instance's **Public IPv4 address** and open
`http://<that address>` (http, not https).

If the page doesn't load, open the instance, **Connect -> EC2 Instance Connect -> Connect**, and run:

```
sudo tail -50 /var/log/cloud-init-output.log
```

## Updating after a new push

From EC2 Instance Connect:

```
cd /opt/paralitrace && sudo git pull && cd frontend && sudo npm run build && sudo systemctl restart paralitrace
```

## Cost

t3.micro is covered by the free tier credits. Stop the instance after judging.
