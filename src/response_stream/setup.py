from setuptools import find_packages, setup

package_name = 'response_stream'

setup(
    name=package_name,
    version='0.0.0',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name]
        ),
        (
            'share/' + package_name,
            ['package.xml']
        ),
    ],

    install_requires=['setuptools'],
    zip_safe=True,

    maintainer='ismail',
    maintainer_email='ismailhsanprsnl@gmail.com',

    description='ROS 2 response stream subscriber',
    license='TODO: License declaration',

    extras_require={
        'test': [
            'pytest',
        ],
    },

    entry_points={
        'console_scripts': [
            'stream_subscriber = response_stream.stream_subs:main',
        ],
    },
)