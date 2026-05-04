from setuptools import find_packages, setup


setup(
    name="stencilforge",
    version="0.5.0",
    description="Fast PCB stencil model generator (Gerber -> STL)",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "mapbox-earcut==2.0.0",
        "pcb-tools==0.1.6",
        "cadquery==2.7.0",
        "numpy>=2.0,<3.0",
        "matplotlib==3.10.8",
        "scipy>=1.10,<2.0",
        "scikit-image==0.26.0",
        "PySide6==6.10.1",
        "shapely==2.1.2",
        "trimesh==4.12.1",
        "vtk==9.6.1",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "stencilforge=stencilforge.cli:main",
            "stencilforge-ui=stencilforge.ui.app:main",
            "stencilforge-ui-vtk=stencilforge.ui.vtk_app:main",
        ]
    },
)
