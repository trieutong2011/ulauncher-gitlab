"""Ulauncher GitLab."""

import logging
import re
import gitlab
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.action.CopyToClipboardAction import \
    CopyToClipboardAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.OpenUrlAction import OpenUrlAction
from ulauncher.api.shared.action.RenderResultListAction import \
    RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.event import (KeywordQueryEvent, PreferencesEvent,
                                        PreferencesUpdateEvent, ItemEnterEvent)
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem

LOGGER = logging.getLogger(__name__)

PROJECTS_SEARCH_TYPE_PUBLIC = "PUBLIC"
PROJECTS_SEARCH_TYPE_MEMBER = "MEMBER"
PROJECTS_SEARCH_TYPE_STARRED = "STARRED"


class GitLabExtension(Extension):
    """Main extension class."""

    def __init__(self):
        """init method."""
        LOGGER.info("Initializing GitLab Extension")
        super(GitLabExtension, self).__init__()

        # initializes GitLab Client
        self.gitlab = None
        self.current_user = None

        # Event listeners
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        self.subscribe(PreferencesEvent, PreferencesEventListener())
        self.subscribe(PreferencesUpdateEvent,
                       PreferencesUpdateEventListener())

    def show_menu(self):
        """Show the main extension menu when the user types the extension
        keyword without arguments."""
        keyword = self.preferences["kw"]

        menu = [
            ExtensionResultItem(
                icon="images/icon.png",
                name="Overview",
                description="",
                highlightable=False,
                on_enter=SetUserQueryAction("%s overview" % keyword),
            ),
            ExtensionResultItem(
                icon="images/icon.png",
                name="Pipelines",
                description="List running pipelines",
                highlightable=False,
                on_enter=SetUserQueryAction("%s pipelines " % keyword),
            ),
            ExtensionResultItem(
                icon="images/icon.png",
                name="Merge Requests",
                description="List opened merge request",
                highlightable=False,
                on_enter=SetUserQueryAction("%s mr" % keyword),
            ),
            # ExtensionResultItem(
            #     icon="images/icon.png",
            #     name="Projects (Starred)",
            #     description="List your starred projects",
            #     highlightable=False,
            #     on_enter=SetUserQueryAction("%s starred " % keyword),
            # ),
        ]

        return RenderResultListAction(menu)

    def show_overview_menu(self, query):
        """Show "Overview" Menu.

        Groups, Starred, etc
        """

        keyword = self.preferences["kw"]
        gitlab_url = self.preferences["url"]

        # Authenticate the user, if its not already authenticated.
        if self.current_user is None:
            self.gitlab.auth()
            self.current_user = self.gitlab.user

        items = [
            ExtensionResultItem(
                icon="images/icon.png",
                name="Gitlab",
                description='Open gitlab',
                highlightable=False,
                on_enter=OpenUrlAction(
                    "%s" % (gitlab_url)),
            ),
            ExtensionResultItem(
                icon="images/icon.png",
                name="My Groups",
                description="List the groups you belong",
                highlightable=False,
                on_enter=SetUserQueryAction("%s groups " % keyword),
                on_alt_enter=CopyToClipboardAction("%s/dashboard/groups" %
                                                   gitlab_url),
            ),
            ExtensionResultItem(
                icon="images/icon.png",
                name="My Access Tokens",
                description='Open "Access Tokens" page',
                highlightable=False,
                on_enter=OpenUrlAction("%s/-/user_settings/personal_access_tokens" % (gitlab_url)),
            ),
        ]

        if query:
            items = [p for p in items if query.lower() in p.get_name().lower()]

        return RenderResultListAction(items)

    def search_projects_for_pipeline(self, query):
        """Search projects in GitLab."""

        projects = self.gitlab.projects.list(
            search=query,
            membership=1,
            order_by="name",
            sort="asc",
            simple=1,
            page=1,
            per_page=10,
        )

        if not projects:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon="images/icon.png",
                    name="No projects found matching your search criteria",
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            ])

        items = []
        for project in projects:
            if project.description is not None:
                description = project.description
            else:
                description = ""

            items.append(
                ExtensionResultItem(
                    icon="images/icon.png",
                    name=project.name,
                    description=description,
                    highlightable=False,
                    on_enter=ExtensionCustomAction(project, keep_app_open=True),
                ))

        return RenderResultListAction(items)

    def search_projects(self, query, search_type):
        """Search projects in GitLab."""

        if search_type == PROJECTS_SEARCH_TYPE_MEMBER:
            projects = self.gitlab.projects.list(
                search=query,
                membership=1,
                order_by="name",
                sort="asc",
                simple=1,
                page=1,
                per_page=10,
            )
        elif search_type == PROJECTS_SEARCH_TYPE_STARRED:
            projects = self.gitlab.projects.list(
                search=query,
                order_by="last_activity_at",
                sort="desc",
                starred=1,
                simple=1,
                page=1,
                per_page=10,
            )
        else:
            projects = self.gitlab.projects.list(
                search=query,
                visibility="public",
                order_by="last_activity_at",
                sort="desc",
                simple=1,
                page=1,
                per_page=10,
            )

        if not projects:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon="images/icon.png",
                    name="No projects found matching your search criteria",
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            ])

        items = []
        for project in projects:
            if project.description is not None:
                description = project.description
            else:
                description = ""
            items.append(
                ExtensionResultItem(
                    icon="images/icon.png",
                    name=project.name,
                    description=description,
                    highlightable=False,
                    on_enter=OpenUrlAction(project.web_url),
                    on_alt_enter=CopyToClipboardAction(project.web_url),
                ))

        return RenderResultListAction(items)

    def list_groups(self, query):
        """Lists the groups the user belongs to."""

        items = []
        groups = self.gitlab.groups.list(archived=0,
                                         search=query,
                                         order_by="name",
                                         sort="asc",
                                         page=1,
                                         per_page=10)

        if not groups:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon="images/icon.png",
                    name="No groups found matching your search criteria",
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            ])

        for group in groups:
            if group.description is not None:
                description = group.description
            else:
                description = ""

            items.append(
                ExtensionResultItem(
                    icon="images/icon.png",
                    name=group.name,
                    description=description,
                    highlightable=False,
                    on_enter=OpenUrlAction(group.web_url),
                    on_alt_enter=CopyToClipboardAction(group.web_url),
                ))

        return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):

    def on_event(self, event, extension):
        # event is instance of ItemEnterEvent

        data = event.get_data()
        # do additional actions here...

        items = []
        pipelines = data.pipelines.list(order_by='updated_at', status='running')

        if not pipelines:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon="images/icon.png",
                    name="No pipelines found",
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            ])

        for pipeline in pipelines:
            if pipeline.name is not None:
                description = pipeline.name
            else:
                description = ""

            items.append(
                ExtensionResultItem(
                    icon="images/icon.png",
                    name=f"{pipeline.source}/{pipeline.ref}",
                    description=description,
                    highlightable=False,
                    on_enter=OpenUrlAction(pipeline.web_url),
                    on_alt_enter=CopyToClipboardAction(pipeline.web_url),
                ))

        return RenderResultListAction(items)

# # pylint: disable=too-many-return-statements


class KeywordQueryEventListener(EventListener):
    """Handles Keyboard input."""

    def on_event(self, event, extension):
        """Handles the event."""

        query = event.get_argument() or ""

        if not query:
            return extension.show_menu()

        # Get the action based on the search terms
        overview = re.findall(r"^overview(.*)?$", query, re.IGNORECASE)
        pipelines = re.findall(r"^pipelines(.*)?$", query, re.IGNORECASE)
        merge_requests = re.findall(r"^mr(.*)?$", query, re.IGNORECASE)
        repos = re.findall(r"^projects(.*)?$", query, re.IGNORECASE)
        groups = re.findall(r"^groups(.*)?$", query, re.IGNORECASE)
        # starred = re.findall(r"^starred(.*)?$", query, re.IGNORECASE)

        try:
            if overview:
                return extension.show_overview_menu(overview[0])

            if repos:
                return extension.search_projects(repos[0],
                                                 PROJECTS_SEARCH_TYPE_MEMBER)

            if pipelines:
                return extension.search_projects_for_pipeline(pipelines[0])

            if merge_requests:
                return extension.list_merge_requests(merge_requests[0])

            if groups:
                return extension.list_groups(groups[0])

            # if starred:
            #     return extension.search_projects(starred[0],
            #                                      PROJECTS_SEARCH_TYPE_STARRED)

            return extension.search_projects(query,
                                             PROJECTS_SEARCH_TYPE_MEMBER)

        except gitlab.GitlabError as exc:
            LOGGER.error(exc)
            return RenderResultListAction([
                ExtensionResultItem(
                    icon="images/icon.png",
                    name="An error ocurred when connecting to GitLab",
                    description=str(exc),
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            ])


class PreferencesEventListener(EventListener):
    """Listener for prefrences event.

    It is triggered on the extension start with the configured
    preferences
    """

    def on_event(self, event, extension):
        """Initializes the GitLab client."""
        extension.gitlab = gitlab.Gitlab(
            event.preferences["url"],
            private_token=event.preferences["access_token"])

        # save the logged in user.
        try:
            extension.gitlab.auth()
            extension.current_user = extension.gitlab.user
        except Exception as exc:
            LOGGER.error(exc)
            extension.current_user = None


class PreferencesUpdateEventListener(EventListener):
    """Listener for "Preferences Update" event.

    It is triggered when the user changes any setting in preferences
    window
    """

    def on_event(self, event, extension):
        if event.id == "url":
            extension.gitlab.url = event.new_value
        elif event.id == "access_token":
            extension.gitlab = gitlab.Gitlab(extension.preferences["url"],
                                             private_token=event.new_value)

            # save the logged in user.
            try:
                extension.gitlab.auth()
                extension.current_user = extension.gitlab.user
            except Exception as exc:
                LOGGER.error(exc)
                extension.current_user = None


if __name__ == "__main__":
    GitLabExtension().run()
