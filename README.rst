Python Project Template
=======================

Repository template to bootstrap a Python project.

Benefits of this template
-------------------------

* Installs Python dependencies from Artifactory under ``.venv/``.
* Installs the expected Python version also under ``.venv/``.
* Pins dependency versions in ``uv.lock``.
* Provides default template for pull requests.
* Checks for syntax and format on pull requests.
* Runs tests on pull requests.
* Publishes to Artifactory when creating tags.
* Pushes documentation to GitHub pages also when creating tags.
* Includes settings for editors and some specifically for VSCode.

Creating a new repository
-------------------------

To create the repository for a new project:

1. On `GitHub`_, navigate to the main page of this repository.
2. Above the file list, click *Use this template*.
3. Select *Create a new repository*.
4. Follow the usual steps.

.. _GitHub: https://github.com/rio-tinto

Configuring the GitHub repository
---------------------------------

In GitHub -> Settings:

1. General:

   * Uncheck ``Wikis``
   * Uncheck ``Projects``
   * Check ``Automatically delete head branches``

2. Collaborators and teams:

   * Add ``everyone`` team with the ``Maintain`` role.
   * Add ``rt-appsec-team-pace`` team with the ``Write`` role.

3. Branch protection rules:

   * Branch name pattern: ``main``
   * Check ``Require a pull request before merging``
   * Check ``Require review from Code Owners``
   * Check ``Require status checks to pass before merging``
   * Click on ``Create``

4. Another branch protection rules:

   * Branch name pattern: ``gh-pages``
   * Check ``Allow force pushes``
   * Click on ``Create``

5. Create branch named ``gh-pages``.

In the source:

1. Rename the directories and config files:

   * Run ``python rename_script.py``
   * Delete ``rename_script.py`` and ``tests/unit/test_rename_script.py``.

2. Rewrite this ``README.rst``. If you rename it to ``README.md`` to use markdown, make sure to update ``pyproject.toml`` too.

3. Email `Solution Advisory`_ to create "GHA_ARTIFACTORY_USERNAME" and "GHA_ARTIFACTORY_PASSWORD" secrets. Make sure to mention:

   * The name of the repository.
   * PyPI read permission.
   * PyPI write permission if you want to publish a package.
   * Docker read permission if you need to pull images, e.g. when testing.
   * Docker write permission if you need to push an image.

.. _Python namespace package: https://packaging.python.org/en/latest/guides/packaging-namespace-packages/
.. _Solution Advisory: solutionadvisory@riotinto.com

Configuring the Azure repository
--------------------------------

1. Create pipeline
2. Add branch policy to run the pipeline automatically

Adding Snyk to the repository
-----------------------------

To add Snyk to the new repository:

1. On `Snyk`_, navigate to the *rt_pace_central* organization.
2. In the top-right, click on the *Add projects* button.
3. In the drop-down, select *GitHub*.
4. Search for the name of the new repository - this assumes that ``rt-appsec-team-pace`` was added in the previous section.
5. In the top-right, click on the *Add selected repositories* button - the default settings should be fine when using this Python template.

.. _Snyk: https://app.snyk.io/

Using the new repository
------------------------

1. ``make setup`` to setup the Python environment and install dependencies.
2. ``make check`` to check syntax and formatting.
3. ``make test`` to run tests.
4. ``make docs`` to build documentation.
5. ``uv add [package]`` to install ``[package]`` in ``.venv/``, add it in ``pyproject.toml`` and pin its version in ``uv.lock``.

Maintaining the new repository
------------------------------

1. In the new repository, add the remote template repository - only needs to be done once:

   .. code-block:: text

      > git remote add template https://github.com/rio-tinto/dna-python-template.git

2. Fetch the latest changes and review the log:

   .. code-block:: text

      > git fetch template
      > git log template/main
      ...

3. Cherry pick each revision from the above log command:

   .. code-block:: text

      > git cherry-pick [revno]


References
----------

* `Creating a repository from a template <https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template>`__
