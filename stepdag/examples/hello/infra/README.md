# The hello graph on Step Functions (dev)

Applied by hand, never CI. State: `env:/dev/stepdag-hello` in `snacker-tracker-aws-infra-tfstate`.
Names: `stepdag-hello-dev-*`. Region `ap-southeast-1`.

Every function runs one zip of stepdag and `hello.py`, on the `python3.14` runtime, which already has boto3. (`../Dockerfile` builds the same thing as an image, for when the functions move to images; nothing uses it yet.)

## 1. Render the manifest

```sh
cd stepdag/examples/hello
uv run stepdag manifest hello:defs > infra/manifest.json
```

Adding an asset to `hello.py` and re-rendering is all Terraform needs.

## 2. Build the package

```sh
uv run python infra/package.py      # writes infra/build/hello.zip
```

## 3. Apply

```sh
cd infra
terraform init
terraform workspace select -or-create dev
terraform plan -out=hello.tfplan   # one Lambda per manifest function
terraform apply hello.tfplan
SM=$(terraform output -raw state_machine_arn)
BUCKET=$(terraform output -raw bucket)
```

## 4. Run the acceptance executions

Run them in order, waiting for each to finish (`aws stepfunctions describe-execution --execution-arn … --query status`):

```sh
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-1 --input '{}'
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-2 --input '{}'
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-3 --input '{"fail_check": true}'
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-4 --input '{"force": true}'
```

## 5. Read the results

Each object is `{"pointer": …, "value": …}`:

```sh
aws s3 cp "s3://$BUCKET/fixed/counter.json" -           # after run-1: 1, run-2: 2, run-4: 1
aws s3 cp "s3://$BUCKET/runs/run-1/report.json" -
aws s3 cp "s3://$BUCKET/runs/run-2/report.json" -       # greeting skipped
aws s3 ls "s3://$BUCKET/runs/run-3/"                    # shout and word_count, but no report: run-3 fails at report
aws s3 cp "s3://$BUCKET/runs/run-4/report.json" -
```

Write the results in ticket 08's comments.

## Tear down

```sh
terraform destroy
```
