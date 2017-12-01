"""
AWS SQS Modular Input
"""

from splunksdc.collector import SimpleCollectorV1
from aws_sqs_data_loader import Input


def main():
    SimpleCollectorV1.main(
        Input(),
        description='Collect and index AWS SQS messages',
        arguments={'placeholder': {}},
    )
