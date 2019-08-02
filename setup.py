import setuptools

setuptools.setup(
    name = "meerkat_target_selector",
    version = "0.0.1",
    author = "Tyler Cox",
    author_email = "tyler.a.cox@asu.edu",
    description = ("Breakthrough Listen's MeerKAT Target Selector"),
    license = "MIT",
    keywords = "example documentation tutorial",
    long_description=open("README.md").read(),
    packages=[
        'mk_target_selector'
        ]
)
