from setuptools import setup, find_packages
setup(
    name='netbox-snmp-plugin',
    version='5.0.0',
    description='NetBox SNMP Inspector — pobieranie i synchronizacja danych urządzeń i interfejsów',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['easysnmp'],
    python_requires='>=3.12',
)
