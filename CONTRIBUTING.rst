How to contribute
=================

Thank you for thinking of contributing!


Reporting issues
----------------

Include the following information in your post:

-   Describe what you expected to happen.
-   If possible, include a `minimal reproducible example`_ to help us
    identify the issue. This also helps check that the issue is not with
    your own code.
-   Describe what actually happened. Include the full traceback if there
    was an exception.
-   List your Python and other versions. If possible, check if this
    issue is already fixed in the latest releases or the latest code in
    the repository.

.. _minimal reproducible example: https://stackoverflow.com/help/minimal-reproducible-example


Setting up
----------

Before submitting patches, you should follow these steps only once to setup your computer:

-   Download and install:

    - `Docker`_
    - `Git`_
    - `Microsoft C++ Build Tools`_ - Check "Desktop development with C++"
    - `Miniconda`_ - Check the box "Add to PATH environment variable"

-   Initialize conda with this command:

    .. code-block:: text

        > conda init powershell
        > conda install --channel conda-forge make poetry

-   Make sure you have a `GitHub account`_.
-   Make sure you can access the https://github.com/rio-tinto organization.
-   Configure git with your `username`_ and `email`_.

    .. code-block:: text

        > git config --global user.name "<your full name>""
        > git config --global user.email <your Rio Tinto email>

-   `Generate new token (classic)`_

    - Note: Rio Tinto
    - Expiration: No expiration
    - Permissions: "repo" and "workflow"

-   Configure git with your token:

    .. code-block:: text

        > git config --global credential.helper manager
        > git clone https://github.com/rio-tinto/<repo name>
        Cloning into '<repo name>'...

    - Select "manager"
    - Check "Always use this from now on" and press "Select"
    - Sign in with token and paste your token

-   `Generate identity token`_ in Artifactory:

    - Click on Welcome button on the top-right.

    - Select Edit Profile from the menu.

    - Click on the Generate an Identity Token button.

-   Create or modify the file ``c:\users\<windows username>\.condarc`` with this content:

    .. code-block:: text

        default_channels:
        - https://artifactory.riotinto.com/artifactory/api/conda/conda

-   Create or modify the file ``c:\users\<windows username>\.netrc`` with this content:

    .. code-block:: text

        machine artifactory.riotinto.com
            login <your Rio Tinto email>
            password <your Artifactory identity token>

-   Create or modify the file ``c:\users\<windows username>\pip\pip.ini`` with this content:

    .. code-block:: text

        [global]
        timeout = 90

-   Configure Docker with your token:

    .. code-block:: text

        > docker login dockerhub.artifactory.riotinto.com
        Username: <your Rio Tinto email>
        Password: <your Artifactory identity token>

.. _docker: https://www.docker.com/products/docker-desktop/
.. _git: https://git-scm.com/download/win
.. _Microsoft C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/
.. _miniconda: https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
.. _username: https://docs.github.com/en/github/using-git/setting-your-username-in-git
.. _email: https://docs.github.com/en/github/setting-up-and-managing-your-github-user-account/setting-your-commit-email-address
.. _GitHub account: https://github.com/join
.. _Generate new token (classic): https://github.com/settings/tokens
.. _Generate identity token: https://artifactory.riotinto.com/ui/admin/artifactory/user_profile


Submitting patches
------------------

If there is not an open issue for what you want to submit, prefer
opening one for discussion before working on a PR. You can work on any
issue that doesn't have an open PR linked to it or a maintainer assigned
to it. These show up in the sidebar. No need to ask if you can work on
an issue that interests you.

Create a pull request:

-   Clone the project:

    .. code-block:: text

        > git clone https://github.com/rio-tinto/<repo name>
        > cd <repo name>

-   Create a new topic branch from the ``main`` branch:

    .. code-block:: text

        > git checkout -b <branch name>

-   Create a virtualenv and install the dependencies:

    .. code-block:: text

        > make setup

-   Commit your changes in logical chunks. Please follow these
    `commit message`_ guidelines or your code is unlikely be merged
    into the main project. Use Git's `interactive rebase`_ feature to
    tidy up your commits before making them public.

-   Follow project style guidelines by making the check target:

    .. code-block:: text

        > poetry install --with check
        > make check

-   Include tests if your patch adds or changes code. Make sure the test
    fails without your patch. Make sure they pass with your patch.

    .. code-block:: text

        > make test

-   Update the apidoc when adding new modules:

    .. code-block:: text

        > poetry install --with docs
        > sphinx-apidoc --force --implicit-namespaces -o docs <project namespace>

-   Add an entry in ``CHANGES.rst``. Use the same style as other
    entries.

-   Push your topic branch up to your fork:

    .. code-block:: text

        > git push origin <branch name>

-   Open a `pull request`_ and follow the instructions in the description.

.. _pull request: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests
.. _commit message: https://cbea.ms/git-commit/
.. _interactive rebase: https://docs.github.com/en/get-started/using-git/about-git-rebase


Publishing a release
--------------------

If you are a maintainer, you can publish a release of the project to Artifactory:

-   In GitHub, click on the ``Releases`` link in the right menu.
-   Click on the ``Draft a new release`` button.
-   In the ``Choose a tag`` drop-down menu, enter the version of the release.
-   In the ``Release title`` input area, enter the version of the release.
-   In the ``Describe the release`` text area, enter the bullets for this release from the ``CHANGES.rst`` file.
-   Click on the ``Publish release`` button.

Note that there is no need to ``Attach binaries by dropping them here
or selecting them`` because the release GitHub action will automatically
build the release and publish it to Artifactory.


Troubleshooting
---------------

-   .. code-block:: text

        CondaHTTPError: HTTP 500 CONNECTION FAILED for url <https://artifactory.riotinto.com/...>
        Elapsed: 00:07.703663

    The cache is probably corrupt - run ``conda clean -a``.

-   .. code-block:: text

        UnavailableInvalidChannel: HTTP 403 UNAVAILABLE OR INVALID for channel conda <https://artifactory.riotinto.com/...>

    The package might contain a vulnerability - try passing ``--channel conda-forge``.

-   .. code-block:: text

        403 Client Error: Forbidden for url: https://files.pythonhosted.org/packages/...

    The package might need confirmation to download - open the link in your browser and click on "Continue" to allow poetry to download the package on the next try.

-   .. code-block:: text

        CondaHTTPError: HTTP 401 CONNECTION FAILED for url <https://artifactory.riotinto.com/...>
        Elapsed: 00:00.982912

    Make sure your login and password are correct in ``~/.netrc``.

-   .. code-block:: text

        Solving environment: failed

        ResolvePackageNotFound:
          - python=3.9

    The cache is probably corrupt - run ``conda clean -a``.

-   .. code-block:: text

        CondaSSLError: Encountered an SSL error. Most likely a certificate verification issue.

        Exception: HTTPSConnectionPool(host='artifactory.riotinto.com', port=443): Max retries exceeded with url: /artifactory/api/conda/conda/win-64/repodata.json (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1006)')))

    or

    .. code-block:: text

        Caused by SSLError(SSLEOFError(8, 'EOF occurred in violation of protocol (_ssl.c:1002)'))

    Zscaler is probably turned off or logged out - authenticate to Zscaler.
