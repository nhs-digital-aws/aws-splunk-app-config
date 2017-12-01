__author__ = 'pezhang'

RI_HOURS_PURCHASED = 'RI_hours_purchased'
RI_HOURS_USED = 'RI_hours_used'
RI_UNITS_PURCHASED = 'RI_units_purchased'
RI_UNITS_USED = 'RI_units_used'
INSTANCE_HOURS_PURCHASED = 'instance_hours_purchased'
INSTANCE_HOURS_COVERED = 'instance_hours_covered'
INSTANCE_UNITS_PURCHASED = 'instance_units_purchased'
INSTANCE_UNITS_COVERED = 'instance_units_covered'

# source page : https://aws.amazon.com/blogs/aws/new-instance-size-flexibility-for-ec2-reserved-instances/
NORMAL_FACTOR = {
    'nano': 0.25,
    'micro': 0.5,
    'small': 1,
    'medium': 2,
    'large': 4,
    'xlarge': 8,
    '2xlarge': 16,
    '4xlarge': 32,
    '8xlarge': 64,
    '10xlarge': 80,
    '16xlarge': 128,
    '32xlarge': 256
}
CAL_ORDER = ['32xlarge', '16xlarge', '10xlarge', '8xlarge', '4xlarge', '2xlarge', 'xlarge', 'large', 'medium', 'small',
             'micro', 'nano']
DELIMITERS = ['\d+', '\W+', '_']
WORDS_MAP = {
    'suse': 'suse',
    'red': 'rhel',
    'hat': 'rhel',
    'rhel': 'rhel',
    'redhat': 'rhel',
    'enterprise': 'enterprise',
    'std': 'std',
    'standard': 'std',
    'wins': 'windows',
    'sql': 'sql',
    'web': 'web',
    'windows': 'windows',
    'server': 'server'
}
PLATFORM_MAP = {
    'SUSE Linux': ['suse'],
    'Red Hat Enterprise Linux': ['rhel'],
    'Windows with SQL Server Standard': ['sql','std', 'windows'],
    'Windows with SQL Server Web': ['sql', 'web', 'windows'],
    'Windows with SQL Server Enterprise': ['enterprise', 'sql', 'windows']
}

PLATFORM_ORDER = ['Windows with SQL Server Standard', 'Windows with SQL Server Web',
                  'Windows with SQL Server Enterprise', 'SUSE Linux', 'Red Hat Enterprise Linux']
