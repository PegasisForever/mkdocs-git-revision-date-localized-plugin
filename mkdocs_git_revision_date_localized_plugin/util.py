# standard library
import logging
import os
import time
from datetime import datetime

# 3rd party
from babel.dates import format_date, get_timezone
from git import Repo, Git, GitCommandError, GitCommandNotFound


class Util:
    def __init__(self, path: str = ".", config={}):

        self.fallback_enabled = False

        try:
            git_repo = Repo(path, search_parent_directories=True)
            self.repo = git_repo.git
        except:
            if config.get("fallback_to_build_date"):
                self.fallback_enabled = True
                logging.warning(
                    "[git-revision-date-localized-plugin] Unable to find a git directory and/or git is not installed."
                    " Option 'fallback_to_build_date' set to 'true': Falling back to build date"
                )
                return None
            else:
                logging.error(
                    "[git-revision-date-localized-plugin] Unable to find a git directory and/or git is not installed."
                    " To ignore this error, set option 'fallback_to_build_date: true'"
                )
                raise

        # Checks if user is running builds on CI
        # See https://github.com/timvink/mkdocs-git-revision-date-localized-plugin/issues/10
        if is_shallow_clone(self.repo):
            n_commits = commit_count(self.repo)

            if os.environ.get("GITLAB_CI") and n_commits < 50:
                # Default is GIT_DEPTH of 50 for gitlab
                logging.warning(
                    """
                       Running on a gitlab runner might lead to wrong git revision dates
                       due to a shallow git fetch depth.
                       Make sure to set GIT_DEPTH to 1000 in your .gitlab-ci.yml file.
                       (see https://docs.gitlab.com/ee/user/project/pipelines/settings.html#git-shallow-clone).
                       """
                )
            if os.environ.get("GITHUB_ACTIONS") and n_commits == 1:
                # Default is fetch-depth of 1 for github actions
                logging.warning(
                    """
                       Running on github actions might lead to wrong git revision dates
                       due to a shallow git fetch depth.
                       Try setting fetch-depth to 0 in your github action
                       (see https://github.com/actions/checkout).
                       """
                )

            # TODO add bitbucket

    @staticmethod
    def _date_formats(
        unix_timestamp: float, locale: str = "en", time_zone: str = "UTC"
    ) -> dict:
        """
        Returns different date formats / types.

        Args:
            unix_timestamp (float): a timestamp in seconds since 1970
            locale (str): Locale code of language to use. Defaults to 'en'.
            time_zone (str): timezone database name (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

        Returns:
            dict: different date formats
        """
        utc_revision_date = datetime.utcfromtimestamp(int(unix_timestamp))
        loc_revision_date = utc_revision_date.replace(
            tzinfo=get_timezone("UTC")
        ).astimezone(get_timezone(time_zone))

        return {
            "date": format_date(loc_revision_date, format="long", locale=locale),
            "datetime": format_date(loc_revision_date, format="long", locale=locale)
            + " "
            + loc_revision_date.strftime("%H:%M:%S"),
            "iso_date": loc_revision_date.strftime("%Y-%m-%d"),
            "iso_datetime": loc_revision_date.strftime("%Y-%m-%d %H:%M:%S"),
            "timeago": "<span class='timeago' datetime='%s' locale='%s'></span>"
            % (loc_revision_date.isoformat(), locale),
        }

    def get_revision_date_for_file(
        self,
        path: str,
        locale: str = "en",
        time_zone: str = "UTC",
        fallback_to_build_date: bool = False,
    ) -> dict:
        """
        Determine localized date variants for a given file

        Args:
            path (str): Location of a markdownfile that is part of a GIT repository
            locale (str, optional): Locale code of language to use. Defaults to 'en'.
            timezone (str): timezone database name (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) 

        Returns:
            dict: localized date variants
        """

        unix_timestamp = None

        # perform git log operation
        try:
            if not self.fallback_enabled:
                # Retrieve author date in UNIX format (%at)
                # https://git-scm.com/docs/git-log#Documentation/git-log.txt-ematem
                unix_timestamp = self.repo.log(path, n=1, date="short", format="%at")

        except GitCommandError as err:
            if fallback_to_build_date:
                logging.warning(
                    "[git-revision-date-localized-plugin] Unable to read git logs of '%s'. Is git log readable?"
                    " Option 'fallback_to_build_date' set to 'true': Falling back to build date"
                    % path
                )
            else:
                logging.error(
                    "[git-revision-date-localized-plugin] Unable to read git logs of '%s'. "
                    " To ignore this error, set option 'fallback_to_build_date: true'"
                    % path
                )
                raise err
        except GitCommandNotFound as err:
            if fallback_to_build_date:
                logging.warning(
                    "[git-revision-date-localized-plugin] Unable to perform command: 'git log'. Is git installed?"
                    " Option 'fallback_to_build_date' set to 'true': Falling back to build date"
                )
            else:
                logging.error(
                    "[git-revision-date-localized-plugin] Unable to perform command 'git log'. Is git installed?"
                    " To ignore this error, set option 'fallback_to_build_date: true'"
                )
                raise err

        # create timestamp
        if not unix_timestamp:
            unix_timestamp = time.time()
            if not self.fallback_enabled:
                logging.warning(
                    "[git-revision-date-localized-plugin] '%s' has no git logs, using current timestamp"
                    % path
                )

        return self._date_formats(
            unix_timestamp=unix_timestamp, time_zone=time_zone, locale=locale
        )


def is_shallow_clone(repo: Git) -> bool:
    """
    Helper function to determine if repository
    is a shallow clone.

    References:
    https://github.com/timvink/mkdocs-git-revision-date-localized-plugin/issues/10
    https://stackoverflow.com/a/37203240/5525118

    Args:
        repo (git.Repo): Repository

    Returns:
        bool: If a repo is shallow clone
    """
    return os.path.exists(".git/shallow")


def commit_count(repo: Git) -> bool:
    """
    Helper function to determine the number of commits in a repository

    Args:
        repo (git.Repo): Repository

    Returns:
        count (int): Number of commits
    """
    refs = repo.for_each_ref().split("\n")
    refs = [x.split()[0] for x in refs]

    counts = [int(repo.rev_list(x, count=True, first_parent=True)) for x in refs]
    return max(counts)
