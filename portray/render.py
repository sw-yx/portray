"""Defines how to render the current project and project_config using the
included documentation generation utilities.
"""
import os
import shutil
import tempfile
from argparse import Namespace
from contextlib import contextmanager
from glob import glob

import mkdocs.config as mkdocs_config
import mkdocs.exceptions as _mkdocs_exceptions
import pdoc.cli
from mkdocs.commands.build import build as mkdocs_build

from portray.exceptions import DocumentationAlreadyExists

def documentation(config, overwrite: bool = False):
    """Renders the entire project given the project config into the config's
    specified output directory.

    Behind the scenes:

    - A temporary directory is created and your code is copy and pasted there
    - pdoc is ran over your code with the output sent into the temporary directory
        as Markdown documents
    - MkDocs is ran over all of your projects Markdown documents including those
        generated py pdoc. MkDocs outputs an HTML representation to a new temporary
        directory.
    - The html temporary directory is copied into your specified output location
    - Both temporary directories are deleted.
    """
    if os.path.exists(config["output_dir"]):
        if overwrite:
            shutil.rmtree(config["output_dir"])
        else:
            raise DocumentationAlreadyExists(config["output_dir"])

    with documentation_in_temp_folder(config) as documentation_output:
        shutil.copytree(documentation_output, config["output_dir"])


def pdoc3(config):
    """Render this project using the specified pdoc config passed into pdoc.

    This rendering is from code definition to Markdown so that
    it will be compatible with MkDocs.
    """
    pdoc.cli.main(Namespace(**config))


def mkdocs(config):
    """Render the project's associated Markdown documentation using the specified
    MkDocs config passed into the MkDocs `build` command.

    This rendering is from `.md` Markdown documents into HTML
    """
    config_instance = _mkdocs_config(config)
    return mkdocs_build(config_instance)


@contextmanager
def documentation_in_temp_folder(config):
    """Build documentation within a temp folder, returning that folder name before it is deleted."""
    with tempfile.TemporaryDirectory() as input_dir:
        input_dir = os.path.join(input_dir, "input")
        with tempfile.TemporaryDirectory() as temp_output_dir:
            shutil.copytree(config["directory"], input_dir)

            if not "output_dir" in config["pdoc3"]:
                config["pdoc3"]["output_dir"] = os.path.join(input_dir, "reference")
            pdoc3(config["pdoc3"])

            if not "docs_dir" in config["mkdocs"]:
                config["mkdocs"]["docs_dir"] = input_dir
            if not "site_dir" in config["mkdocs"]:
                config["mkdocs"]["site_dir"] = temp_output_dir
            if not "nav" in config["mkdocs"]:
                nav = config["mkdocs"]["nav"] = []

                root_docs = glob(os.path.join(input_dir, "*.md"))
                readme_doc = os.path.join(input_dir, "README.md")
                if readme_doc in root_docs:
                    root_docs.remove(readme_doc)
                    nav.append({"Home": "README.md"})
                nav.extend(_doc(doc, input_dir, config) for doc in root_docs)

                docs_dir_docs = glob(os.path.join(input_dir, config["docs_dir"], "*.md"))
                nav.extend(
                    _nested_docs(os.path.join(input_dir, config["docs_dir"]), input_dir, config)
                )

                reference_docs = glob(os.path.join(config["pdoc3"]["output_dir"], "**/*.md"))
                nav.append(
                    {"Reference": _nested_docs(config["pdoc3"]["output_dir"], input_dir, config)}
                )

            mkdocs(config["mkdocs"])
            yield temp_output_dir


def _mkdocs_config(config):
    config_instance = mkdocs_config.Config(schema=mkdocs_config.DEFAULT_SCHEMA)
    config_instance.load_dict(config)

    errors, warnings = config_instance.validate()
    if errors:
        raise _mkdocs_exceptions.ConfigurationError(
            "Aborted with {} Configuration Errors!".format(len(errors))
        )
    elif config.get("strict", False) and warnings:
        raise _mkdocs_exceptions.ConfigurationError(
            "Aborted with {} Configuration Warnings in 'strict' mode!".format(len(warnings))
        )

    config_instance.config_file_path = config["config_file_path"]
    return config_instance


def _nested_docs(directory, root_directory, config) -> list:
    nav = [_doc(doc, root_directory, config) for doc in glob(os.path.join(directory, "*.md"))]

    nested_dirs = glob(os.path.join(directory, "*/"))
    for nested_dir in nested_dirs:
        nav.append(
            {_label(nested_dir[:-1], config): _nested_docs(nested_dir, root_directory, config)}
        )

    return nav


def _label(path, config):
    auto = os.path.basename(path).split(".")[0].replace("-", " ").replace("_", " ").title()
    return config["labels"].get(auto, auto)


def _doc(path, root_path, config):
    path = os.path.relpath(path, root_path)
    return {_label(path, config): path}
