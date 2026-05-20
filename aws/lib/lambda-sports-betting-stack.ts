import * as cdk from "aws-cdk-lib";
import { CfnOutput, Duration, SecretValue, Stack, type StackProps } from "aws-cdk-lib";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export class LambdaSportsBettingStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const bucketName = this.node.tryGetContext("bucketName") || process.env.SPORTSBETTING_S3_BUCKET;
    if (!bucketName) {
      throw new Error("SPORTSBETTING_S3_BUCKET or -c bucketName=... is required");
    }
    const kalshiSecretName =
      this.node.tryGetContext("kalshiSecretName") || process.env.KALSHI_SECRET_NAME || "sportsbetting/kalshi";

    const dataBucket = s3.Bucket.fromBucketName(this, "SportsBettingDataBucket", bucketName);
    const kalshiSecret = new secretsmanager.Secret(this, "KalshiCredentialsSecret", {
      secretName: kalshiSecretName,
      description: "Kalshi API credentials for sports betting Lambda execution. Fill values manually after deploy.",
      secretStringValue: SecretValue.unsafePlainText(
        JSON.stringify(
          {
            KALSHI_API_KEY_ID: "replace-me",
            KALSHI_PRIVATE_KEY_PEM: "replace-me",
            KALSHI_BASE_URL: "https://external-api.kalshi.com/trade-api/v2",
            KALSHI_ALLOW_LIVE_TRADING: "false",
          },
          null,
          2,
        ),
      ),
    });
    const lambdaCode = lambda.Code.fromAsset("..", {
      bundling: {
        image: lambda.Runtime.PYTHON_3_11.bundlingImage,
        command: [
          "bash",
          "-lc",
          [
            "python -m pip install -r aws/lambdas/requirements.txt -t /asset-output",
            "mkdir -p /asset-output/aws /asset-output/execution /asset-output/kalshi /asset-output/strategy",
            "cp -R aws/helpers aws/lambdas aws/__init__.py /asset-output/aws/",
            "cp -R execution/cli execution/core execution/kalshi execution/schedules execution/__init__.py execution/interface.py /asset-output/execution/",
            "cp -R kalshi/markets kalshi/trading kalshi/__init__.py kalshi/interface.py /asset-output/kalshi/",
            "cp -R strategy/core strategy/helpers strategy/mlb strategy/wrappers strategy/__init__.py strategy/interface.py /asset-output/strategy/",
          ].join(" && "),
        ],
      },
    });

    const commonEnvironment = {
      SPORTSBETTING_S3_BUCKET: bucketName,
    };
    const runStrategyEnvironment = {
      ...commonEnvironment,
      KALSHI_SECRET_NAME: kalshiSecret.secretName,
    };

    const statusFunction = new lambda.Function(this, "RefreshTradeStatusFunction", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "aws.lambdas.status.lambda_handler",
      code: lambdaCode,
      timeout: Duration.minutes(10),
      memorySize: 512,
      environment: commonEnvironment,
    });

    const exportFunction = new lambda.Function(this, "ExportStatusJsonFunction", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "aws.lambdas.export_status_json.lambda_handler",
      code: lambdaCode,
      timeout: Duration.minutes(5),
      memorySize: 512,
      environment: commonEnvironment,
    });

    const runStrategyFunction = new lambda.Function(this, "RunStrategyFunction", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "aws.lambdas.run_strategy.lambda_handler",
      code: lambdaCode,
      timeout: Duration.minutes(15),
      memorySize: 1024,
      environment: runStrategyEnvironment,
    });

    dataBucket.grantReadWrite(statusFunction, "private/*");
    dataBucket.grantReadWrite(exportFunction, "private/*");
    dataBucket.grantReadWrite(exportFunction, "public/data/*");
    dataBucket.grantReadWrite(runStrategyFunction, "private/*");
    dataBucket.grantReadWrite(runStrategyFunction, "public/data/*");

    kalshiSecret.grantRead(runStrategyFunction);

    if (this.node.tryGetContext("enableSchedules") === "true") {
      const statusRule = new events.Rule(this, "DailyStatusRefreshSchedule", {
        schedule: events.Schedule.cron({ minute: "0", hour: "10" }),
      });
      statusRule.addTarget(new targets.LambdaFunction(statusFunction));

      const exportRule = new events.Rule(this, "DailyStatusExportSchedule", {
        schedule: events.Schedule.cron({ minute: "10", hour: "10" }),
      });
      exportRule.addTarget(new targets.LambdaFunction(exportFunction));
    }

    new CfnOutput(this, "RefreshTradeStatusFunctionName", {
      value: statusFunction.functionName,
    });
    new CfnOutput(this, "ExportStatusJsonFunctionName", {
      value: exportFunction.functionName,
    });
    new CfnOutput(this, "RunStrategyFunctionName", {
      value: runStrategyFunction.functionName,
    });
    new CfnOutput(this, "KalshiCredentialsSecretName", {
      value: kalshiSecret.secretName,
    });
    new CfnOutput(this, "KalshiCredentialsSecretArn", {
      value: kalshiSecret.secretArn,
    });
  }
}
