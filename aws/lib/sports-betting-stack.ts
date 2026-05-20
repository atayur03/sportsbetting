import * as cdk from "aws-cdk-lib";
import { CfnOutput, RemovalPolicy, Stack, type StackProps } from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

export class SportsBettingStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const projectName = this.node.tryGetContext("projectName") || "sportsbetting";
    const bucketName = this.node.tryGetContext("bucketName") || process.env.SPORTSBETTING_S3_BUCKET;

    const dataBucket = new s3.Bucket(this, "SportsBettingDataBucket", {
      bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
      versioned: true,
    });

    const runtimeRole = new iam.Role(this, "SportsBettingRuntimeRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Runtime role for jobs that update sports betting data in S3.",
    });

    runtimeRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
    );
    dataBucket.grantReadWrite(runtimeRole, "private/*");
    dataBucket.grantReadWrite(runtimeRole, "public/data/*");

    const privatePrefix = "private";
    const publicStatusJsonKey = "public/data/trade-status.json";

    const websiteStatusApiUser = new iam.User(this, "WebsiteStatusApiUser");
    websiteStatusApiUser.addToPolicy(
      new iam.PolicyStatement({
        sid: "ReadSanitizedStatusJson",
        actions: ["s3:GetObject"],
        resources: [dataBucket.arnForObjects(publicStatusJsonKey)],
      }),
    );
    websiteStatusApiUser.addToPolicy(
      new iam.PolicyStatement({
        sid: "ListSanitizedStatusJson",
        actions: ["s3:ListBucket"],
        resources: [dataBucket.bucketArn],
        conditions: {
          StringEquals: {
            "s3:prefix": publicStatusJsonKey,
          },
        },
      }),
    );

    new CfnOutput(this, "BucketName", {
      value: dataBucket.bucketName,
    });
    new CfnOutput(this, "PrivatePrefix", {
      value: privatePrefix,
    });
    new CfnOutput(this, "PublicStatusJsonS3Uri", {
      value: `s3://${dataBucket.bucketName}/${publicStatusJsonKey}`,
    });
    new CfnOutput(this, "WebsiteStatusApiPath", {
      value: "/api/status",
    });
    new CfnOutput(this, "WebsiteStatusApiUserName", {
      value: websiteStatusApiUser.userName,
    });
    new CfnOutput(this, "WebsiteStatusApiUserArn", {
      value: websiteStatusApiUser.userArn,
    });
    new CfnOutput(this, "RuntimeRoleArn", {
      value: runtimeRole.roleArn,
    });

    cdk.Tags.of(this).add("Project", projectName);
    cdk.Tags.of(this).add("ManagedBy", "cdk");
  }
}
