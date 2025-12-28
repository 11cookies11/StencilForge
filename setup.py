from setuptools import find_packages, setup


setup(
    name="stencilforge",
    version="0.1.0",
    description="Fast PCB stencil model generator (Gerber -> STL)",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "mapbox-earcut==1.0.1",
        "pcb-tools==0.1.6",
        "cadquery==2.4.0",
        "numpy<2.0",
        "PySide6==6.10.1",
        "shapely==2.1.2",
        "trimesh==4.10.1",
        "vtk==9.3.0",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "stencilforge=stencilforge.cli:main",
            "stencilforge-ui=stencilforge.ui_app:main",
            "stencilforge-ui-vtk=stencilforge.ui_vtk_app:main",
        ]
    },
)
