from setuptools import find_packages, setup


setup(
    name="stencilforge",
    version="0.1.0",
    description="Fast PCB stencil model generator (Gerber -> STL)",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "pcb-tools==0.1.6",
        "PySide6==6.10.1",
        "shapely==2.1.2",
        "trimesh==4.10.1",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "stencilforge=stencilforge.cli:main",
            "stencilforge-ui=stencilforge.ui_app:main",
        ]
    },
)
