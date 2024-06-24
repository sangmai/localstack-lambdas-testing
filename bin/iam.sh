awslocal iam create-role --role-name super-role --assume-role-policy-document '
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "*",
      "Effect": "Allow",
      "Resource": "*"
    }
  ]
}'