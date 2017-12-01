"""
Custom REST Endpoint for enumerating AWS regions.
"""

import aws_bootstrap_env


import splunk
import splunk.admin
import json

NAMESPACE_ARG = 'namespace'

_CLOUDWATCH_DEFAULT_METRICS = {
    "AWS/ApiGateway": [
        "5XXError",
        "4XXError",
        "CacheHitCount",
        "CacheMissCount",
        "Count",
        "Latency",
        "IntegrationLatency"
    ],
    "AWS/ApplicationELB": [
        "RequestCount",
        "RequestCountPerTarget",
        "ActiveConnectionCount",
        "ProcessedBytes",
        "TargetConnectionErrorCount",
        "TargetResponseTime",
        "TargetTLSNegotiationErrorCount",
        "HTTPCode_Target_2XX_Count",
        "HTTPCode_Target_3XX_Count",
        "HTTPCode_Target_4XX_Count",
        "HTTPCode_Target_5XX_Count",
        "HTTPCode_ELB_4XX_Count",
        "HTTPCode_ELB_5XX_Count",
        "ClientTLSNegotiationErrorCount",
        "ConsumedLCUs",
        "IPv6ProcessedBytes",
        "IPv6RequestCount",
        "HealthyHostCount",
        "UnHealthyHostCount",
        "NewConnectionCount",
        "RejectedConnectionCount",
        "RuleEvaluations"
    ],
    "AWS/AutoScaling": [
        "GroupDesiredCapacity",
        "GroupInServiceInstances",
        "GroupMaxSize",
        "GroupMinSize",
        "GroupPendingInstances",
        "GroupStandbyInstances",
        "GroupTerminatingInstances",
        "GroupTotalInstances"
    ],
    "AWS/Billing": [
        "EstimatedCharges"
    ],
    "AWS/CloudFront": [
        "4xxErrorRate",
        "5xxErrorRate",
        "BytesDownloaded",
        "BytesUploaded",
        "Requests",
        "TotalErrorRate"
    ],
    "AWS/CloudSearch": [
        "IndexUtilization",
        "Partitions",
        "SearchableDocuments",
        "SuccessfulRequests"
    ],
    "AWS/DynamoDB": [
        "ConditionalCheckFailedRequests",
        "ConsumedReadCapacityUnits",
        "ConsumedWriteCapacityUnits",
        "OnlineIndexConsumedWriteCapacity",
        "OnlineIndexPercentageProgress",
        "OnlineIndexThrottleEvents",
        "ProvisionedReadCapacityUnits",
        "ProvisionedWriteCapacityUnits",
        "ReadThrottleEvents",
        "ReturnedBytes",
        "ReturnedItemCount",
        "ReturnedRecordsCount",
        "SuccessfulRequestLatency",
        "SystemErrors",
        "ThrottledRequests",
        "UserErrors",
        "WriteThrottleEvents"
    ],
    "AWS/EBS": [
        "BurstBalance",
        "VolumeConsumedReadWriteOps",
        "VolumeIdleTime",
        "VolumeQueueLength",
        "VolumeReadBytes",
        "VolumeReadOps",
        "VolumeThroughputPercentage",
        "VolumeTotalReadTime",
        "VolumeTotalWriteTime",
        "VolumeWriteBytes",
        "VolumeWriteOps"
    ],
    "AWS/EC2": [
        "CPUCreditBalance",
        "CPUCreditUsage",
        "CPUUtilization",
        "DiskReadBytes",
        "DiskReadOps",
        "DiskWriteBytes",
        "DiskWriteOps",
        "NetworkIn",
        "NetworkOut",
        "NetworkPacketsIn",
        "NetworkPacketsOut",
        "StatusCheckFailed",
        "StatusCheckFailed_Instance",
        "StatusCheckFailed_System"
    ],
    "AWS/EC2Spot": [
        "AvailableInstancePoolsCount",
        "BidsSubmittedForCapacity",
        "EligibleInstancePoolCount",
        "FulfilledCapacity",
        "MaxPercentCapacityAllocation",
        "PendingCapacity",
        "PercentCapacityAllocation",
        "TargetCapacity",
        "TerminatingCapacity"
    ],
    "AWS/ECS": [
        "CPUReservation",
        "CPUUtilization",
        "MemoryReservation",
        "MemoryUtilization"
    ],
    "AWS/ELB": [
        "BackendConnectionErrors",
        "HTTPCode_Backend_2XX",
        "HTTPCode_Backend_3XX",
        "HTTPCode_Backend_4XX",
        "HTTPCode_Backend_5XX",
        "HTTPCode_ELB_4XX",
        "HTTPCode_ELB_5XX",
        "HealthyHostCount",
        "Latency",
        "RequestCount",
        "SpilloverCount",
        "SurgeQueueLength",
        "UnHealthyHostCount"
    ],
    "AWS/ES": [
        "AutomatedSnapshotFailure",
        "CPUUtilization",
        "ClusterStatus.green",
        "ClusterStatus.red",
        "ClusterStatus.yellow",
        "DeletedDocuments",
        "FreeStorageSpace",
        "JVMMemoryPressure",
        "MasterCPUUtilization",
        "MasterFreeStorageSpace",
        "MasterJVMMemoryPressure",
        "Nodes",
        "ReadIOPS",
        "ReadLatency",
        "ReadThroughput",
        "SearchableDocuments",
        "WriteIOPS",
        "WriteLatency",
        "WriteThroughput",
        "ClusterUsedSpace",
        "ClusterIndexWritesBlocked",
        "CPUCreditBalance",
        "KibanaHealthyNodes",
        "MasterCPUCreditBalance",
        "MasterReachableFromNode",
        "DiskQueueDepth"
    ],
    "AWS/ElastiCache": [
        "BytesReadIntoMemcached",
        "BytesUsedForCache",
        "BytesUsedForCacheItems",
        "BytesUsedForHash",
        "BytesWrittenOutFromMemcached",
        "CPUUtilization",
        "CacheHits",
        "CacheMisses",
        "CasBadval",
        "CasHits",
        "CasMisses",
        "CmdConfigGet",
        "CmdConfigSet",
        "CmdFlush",
        "CmdGet",
        "CmdSet",
        "CmdTouch",
        "CurrConfig",
        "CurrConnections",
        "CurrItems",
        "DecrHits",
        "DecrMisses",
        "DeleteHits",
        "DeleteMisses",
        "EvictedUnfetched",
        "Evictions",
        "ExpiredUnfetched",
        "FreeableMemory",
        "GetHits",
        "GetMisses",
        "GetTypeCmds",
        "HashBasedCmds",
        "HyperLogLogBasedCmds",
        "IncrHits",
        "IncrMisses",
        "KeyBasedCmds",
        "ListBasedCmds",
        "NetworkBytesIn",
        "NetworkBytesOut",
        "NewConnections",
        "NewItems",
        "Reclaimed",
        "ReplicationBytes",
        "ReplicationLag",
        "SaveInProgress",
        "SetBasedCmds",
        "SetTypeCmds",
        "SlabsMoved",
        "SortedSetBasedCmds",
        "StringBasedCmds",
        "SwapUsage",
        "TouchHits",
        "TouchMisses",
        "UnusedMemory"
    ],
    "AWS/ElasticMapReduce": [
        "AppsCompleted",
        "AppsFailed",
        "AppsKilled",
        "AppsPending",
        "AppsRunning",
        "AppsSubmitted",
        "BackupFailed",
        "CapacityRemainingGB",
        "Cluster",
        "ContainerAllocated",
        "ContainerPending",
        "ContainerReserved",
        "CoreNodesPending",
        "CoreNodesRunning",
        "CorruptBlocks",
        "DfsPendingReplicationBlocks",
        "HBase",
        "HDFSBytesRead",
        "HDFSBytesWritten",
        "HDFSUtilization",
        "HbaseBackupFailed",
        "IO",
        "IsIdle",
        "JobsFailed",
        "JobsRunning",
        "LiveDataNodes",
        "LiveTaskTrackers",
        "MRActiveNodes",
        "MRDecommissionedNodes",
        "MRLostNodes",
        "MRRebootedNodes",
        "MRTotalNodes",
        "MRUnhealthyNodes",
        "Map/Reduce",
        "MapSlotsOpen",
        "MapTasksRemaining",
        "MapTasksRunning",
        "MemoryAllocatedMB",
        "MemoryAvailableMB",
        "MemoryReservedMB",
        "MemoryTotalMB",
        "MissingBlocks",
        "MostRecentBackupDuration",
        "Node",
        "PendingDeletionBlocks",
        "ReduceSlotsOpen",
        "ReduceTasksRemaining",
        "ReduceTasksRunning",
        "RemainingMapTasksPerSlot",
        "S3BytesRead",
        "S3BytesWritten",
        "Status",
        "TaskNodesPending",
        "TaskNodesRunning",
        "TimeSinceLastSuccessfulBackup",
        "TotalLoad",
        "UnderReplicatedBlocks",
        "ContainerPendingRatio",
        "YARNMemoryAvailablePercentage"
    ],
    "AWS/Events": [
        "FailedInvocations",
        "Invocations",
        "MatchedEvents",
        "ThrottledRules",
        "TriggeredRules"
    ],
    "AWS/Kinesis": [
        "GetRecords.Bytes",
        "GetRecords.IteratorAge",
        "GetRecords.IteratorAgeMilliseconds",
        "GetRecords.Latency",
        "GetRecords.Records",
        "GetRecords.Success",
        "IncomingBytes",
        "IncomingRecords",
        "PutRecord.Bytes",
        "PutRecord.Latency",
        "PutRecord.Success",
        "PutRecords.Bytes",
        "PutRecords.Latency",
        "PutRecords.Records",
        "PutRecords.Success",
        "ReadProvisionedThroughputExceeded",
        "WriteProvisionedThroughputExceeded"
    ],
    "AWS/Lambda": [
        "Duration",
        "Errors",
        "Invocations",
        "Throttles",
        "IteratorAge"
    ],
    "AWS/Logs": [
        "DeliveryErrors",
        "DeliveryThrottling",
        "ForwardedBytes",
        "ForwardedLogEvents",
        "IncomingBytes",
        "IncomingLogEvents"
    ],
    "AWS/ML": [
        "PredictCount",
        "PredictFailureCount"
    ],
    "AWS/OpsWorks": [
        "cpu_idle",
        "cpu_nice",
        "cpu_system",
        "cpu_user",
        "cpu_waitio",
        "cpu_steal",
        "load_1",
        "load_15",
        "load_5",
        "memory_buffers",
        "memory_cached",
        "memory_free",
        "memory_swap",
        "memory_total",
        "memory_used",
        "procs"
    ],
    "AWS/RDS": [
        "BinLogDiskUsage",
        "CPUCreditBalance",
        "CPUCreditUsage",
        "CPUUtilization",
        "DatabaseConnections",
        "DiskQueueDepth",
        "FreeStorageSpace",
        "FreeableMemory",
        "NetworkReceiveThroughput",
        "NetworkTransmitThroughput",
        "ReadIOPS",
        "ReadLatency",
        "ReadThroughput",
        "ReplicaLag",
        "SwapUsage",
        "WriteIOPS",
        "WriteLatency",
        "WriteThroughput",
        "BurstBalance"
    ],
    "AWS/Redshift": [
        "CPUUtilization",
        "DatabaseConnections",
        "HealthStatus",
        "MaintenanceMode",
        "NetworkReceiveThroughput",
        "NetworkTransmitThroughput",
        "PercentageDiskSpaceUsed",
        "ReadIOPS",
        "ReadLatency",
        "ReadThroughput",
        "WriteIOPS",
        "WriteLatency",
        "WriteThroughput"
    ],
    "AWS/Route53": [
        "ConnectionTime",
        "HealthCheckPercentageHealthy",
        "HealthCheckStatus",
        "SSLHandshakeTime",
        "TimeToFirstByte",
        "ChildHealthCheckHealthyCount"
    ],
    "AWS/S3": [
        "BucketSizeBytes",
        "NumberOfObjects"
    ],
    "AWS/SNS": [
        "NumberOfMessagesPublished",
        "NumberOfNotificationsDelivered",
        "NumberOfNotificationsFailed",
        "PublishSize",
        "SMSSuccessRate"
    ],
    "AWS/SQS": [
        "ApproximateNumberOfMessagesDelayed",
        "ApproximateNumberOfMessagesNotVisible",
        "ApproximateNumberOfMessagesVisible",
        "ApproximateAgeOfOldestMessage",
        "NumberOfEmptyReceives",
        "NumberOfMessagesDeleted",
        "NumberOfMessagesReceived",
        "NumberOfMessagesSent",
        "SentMessageSize"
    ],
    "AWS/SWF": [
        "ActivityTaskScheduleToCloseTime",
        "ActivityTaskScheduleToStartTime",
        "ActivityTaskStartToCloseTime",
        "ActivityTasksCanceled",
        "ActivityTasksCompleted",
        "ActivityTasksFailed",
        "DecisionTaskScheduleToStartTime",
        "DecisionTaskStartToCloseTime",
        "DecisionTasksCompleted",
        "ScheduledActivityTasksTimedOutOnClose",
        "ScheduledActivityTasksTimedOutOnStart",
        "StartedActivityTasksTimedOutOnClose",
        "StartedActivityTasksTimedOutOnHeartbeat",
        "StartedDecisionTasksTimedOutOnClose",
        "WorkflowStartToCloseTime",
        "WorkflowsCanceled",
        "WorkflowsCompleted",
        "WorkflowsContinuedAsNew",
        "WorkflowsFailed",
        "WorkflowsTerminated",
        "WorkflowsTimedOut"
    ],
    "AWS/StorageGateway": [
        "CacheFree",
        "CacheHitPercent",
        "CachePercentDirty",
        "CachePercentUsed",
        "CacheUsed",
        "CloudBytesDownloaded",
        "CloudBytesUploaded",
        "CloudDownloadLatency",
        "QueuedWrites",
        "ReadBytes",
        "ReadTime",
        "TimeSinceLastRecoveryPoint",
        "TotalCacheSize",
        "UploadBufferFree",
        "UploadBufferPercentUsed",
        "UploadBufferUsed",
        "WorkingStorageFree",
        "WorkingStoragePercentUsed",
        "WorkingStorageUsed",
        "WriteBytes",
        "WriteTime"
    ],
    "AWS/WAF": [
        "AllowedRequests",
        "BlockedRequests",
        "CountedRequests"
    ],
    "AWS/WorkSpaces": [
        "Available",
        "ConnectionAttempt",
        "ConnectionFailure",
        "ConnectionSuccess",
        "InSessionLatency",
        "Maintenance",
        "SessionDisconnect",
        "SessionLaunchTime",
        "Unhealthy",
        "UserConnected",
        "Stopped"
    ],
    "AWS/DX": [
        "ConnectionState",
        "ConnectionBpsEgress",
        "ConnectionBpsIngress",
        "ConnectionPpsEgress",
        "ConnectionPpsIngress",
        "ConnectionCRCErrorCount",
        "ConnectionLightLevelTx",
        "ConnectionLightLevelRx"
    ]
}


_CLOUDWATCH_DEFAULT_DIMENSIONS = {
    "AWS/ApiGateway": [
        {
            "ApiName": [".*"]
        },
        {
            "ApiName": [".*"],
            "Stage": [".*"]
        },
        {
            "ApiName": [".*"],
            "Method": [".*"],
            "Resource": [".*"],
            "Stage": [".*"]
        }
    ],
    "AWS/AutoScaling": [
        {
            "AutoScalingGroupName": [".*"]
        }
    ],
    "AWS/ApplicationELB": [
        {
            "LoadBalancer": [".*"]
        },
        {
            "AvailabilityZone": [".*"],
            "LoadBalancer": [".*"]
        },
        {
            "AvailabilityZone": [".*"],
            "TargetGroup": [".*"],
            "LoadBalancer": [".*"]
        }
    ],
    "AWS/Billing": [
        {
            "Currency": [".*"]
        },
        {
            "Currency": [".*"],
            "ServiceName": [".*"]
        },
        {
            "Currency": [".*"],
            "LinkedAccount": [".*"],
            "ServiceName": [".*"]
        }
    ],
    "AWS/CloudFront": [
        {
            "DistributionId": [".*"],
            "Region": "Global"
        }
    ],
    "AWS/CloudSearch": [
        {
            "ClientId": [".*"],
            "DomainName": [".*"]
        }
    ],
    "AWS/DynamoDB": [
        {
            "TableName": [".*"]
        },
        {
            "TableName": [".*"],
            "Operation": [".*"]
        }
    ],
    "AWS/EBS": [
        {
            "VolumeId": [".*"]
        }
    ],
    "AWS/EC2": [
        {
            "AutoScalingGroupName": [".*"]
        },
        {
            "ImageId": [".*"]
        },
        {
            "InstanceId": [".*"]
        },
        {
            "InstanceType": [".*"]
        }
    ],
    "AWS/EC2Spot": [
        {
            "AvailabilityZone": [".*"]
        },
        {
            "FleetRequestId": [".*"]
        },
        {
            "InstanceType": [".*"]
        }
    ],
    "AWS/ECS": [
        {
            "ClusterName": [".*"]
        }
    ],
    "AWS/ELB": [
        {
            "AvailabilityZone": [".*"],
            "LoadBalancerName": [".*"]
        },
        {
            "AvailabilityZone": [".*"]
        },
        {
            "LoadBalancerName": [".*"]
        }
    ],
    "AWS/ES": [
        {
            "ClientId": [".*"],
            "DomainName": [".*"]
        }
    ],
    "AWS/ElastiCache": [
        {
            "CacheClusterId": [".*"],
            "CacheNodeId": [".*"]
        }
    ],
    "AWS/ElasticMapReduce": [
        {
            "JobFlowId": [".*"],
            "JobId": [".*"]
        }
    ],
    "AWS/Events": [
        {
            "RuleName": [".*"]
        }
    ],
    "AWS/Kinesis": [
        {
            "StreamName": [".*"]
        }
    ],
    "AWS/Lambda": [
        {
            "FunctionName": [".*"],
            "Resource": [".*"]
        },
        {
            "FunctionName": [".*"]
        }
    ],
    "AWS/Logs": [
        {
            "DestinationType": [".*"],
            "FilterName": [".*"],
            "LogGroupName": [".*"]
        },
        {
            "LogGroupName": [".*"]
        }
    ],
    "AWS/ML": [
        {
            "MLModelId": [".*"]
        },
        {
            "RequestMode": [".*"]
        }
    ],
    "AWS/OpsWorks": [
        {
            "InstanceId": [".*"]
        },
        {
            "LayerId": [".*"]
        },
        {
            "StackId": [".*"]
        }
    ],
    "AWS/RDS": [
        {
            "DBClusterIdentifier": [".*"]
        },
        {
            "DBInstanceIdentifier": [".*"]
        },
        {
            "DatabaseClass": [".*"]
        },
        {
            "EngineName": [".*"]
        }
    ],
    "AWS/Redshift": [
        {
            "ClusterIdentifier": [".*"]
        },
        {
            "NodeID": [".*"]
        }
    ],
    "AWS/Route53": [
        {
            "HealthCheckId": [".*"]
        }
    ],
    "AWS/S3": [
        {
            "BucketName": [".*"],
            "StorageType": [".*"]
        },
        {
            "BucketName": [".*"],
            "FilterId": [".*"]
        }
    ],
    "AWS/SNS": [
        {
            "TopicName": [".*"]
        }
    ],
    "AWS/SQS": [
        {
            "QueueName": [".*"]
        }
    ],
    "AWS/SWF": [
        {
            "Domain": [".*"],
            "ActionDomain": [".*"],
            "ActionName": [".*"],
            "ActionNamespace": [".*"],
            "ActionVersion": [".*"]
        },
        {
            "ActivityTypeName": [".*"],
            "ActivityTypeVersion": [".*"],
            "Domain": [".*"]
        },
        {
            "WorkflowTypeName": [".*"],
            "WorkflowTypeVersion": [".*"],
            "Domain": [".*"]
        }
    ],
    "AWS/StorageGateway": [
        {
            "GatewayId": [".*"],
            "GatewayName": [".*"]
        },
        {
            "VolumeId": [".*"]
        }
    ],
    "AWS/WAF": [
        {
            "Rule": [".*"],
            "WebACL": [".*"]
        }
    ],
    "AWS/WorkSpaces": [
        {
            "DirectoryId": [".*"],
            "WorkspaceId": [".*"]
        }
    ],
    "AWS/DX": [
        {
            "ConnectionId": [".*"]
        }
    ]
}

_CLOUDWATCH_DEFAULT_STATISTICS = ["Average","Sum","SampleCount","Maximum","Minimum"]

_CLOUDWATCH_DEFAULT_NAMESPACES = ['AWS/ApiGateway', 'AWS/ApplicationELB', 'AWS/Billing',
    'AWS/EBS', 'AWS/EC2', 'AWS/ELB', 'AWS/Lambda', 'AWS/RDS', 'AWS/S3']


class ConfigHandler(splunk.admin.MConfigHandler):

    def setup(self):
        self.supportedArgs.addOptArg(NAMESPACE_ARG)

    def handleList(self, confInfo):
        metrics = _CLOUDWATCH_DEFAULT_METRICS
        dimensions = _CLOUDWATCH_DEFAULT_DIMENSIONS

        if NAMESPACE_ARG in self.callerArgs.data:
            namespace = self.callerArgs.data[NAMESPACE_ARG][0]
            metrics = _CLOUDWATCH_DEFAULT_METRICS.get(namespace)
            dimensions = _CLOUDWATCH_DEFAULT_DIMENSIONS.get(namespace)

        response = confInfo['DefaultSettings']
        response.append('metrics', json.dumps(metrics))
        response.append('dimensions', json.dumps(dimensions))
        response.append('statistics', json.dumps(_CLOUDWATCH_DEFAULT_STATISTICS))
        response.append('namespaces', json.dumps(_CLOUDWATCH_DEFAULT_NAMESPACES))

def main():
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == '__main__':
    main()