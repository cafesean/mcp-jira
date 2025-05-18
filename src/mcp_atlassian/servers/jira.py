"""Jira FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.jira.constants import DEFAULT_READ_JIRA_FIELDS
from mcp_atlassian.models.jira.common import JiraUser

from .context import MainAppContext

logger = logging.getLogger(__name__)

jira_mcp = FastMCP(
    name="Jira MCP Service",
    description="Provides tools for interacting with Atlassian Jira.",
)


@jira_mcp.tool(tags={"jira", "read"})
async def get_user_profile(
    ctx: Context[Any, MainAppContext],
    user_identifier: Annotated[
        str,
        Field(
            description="Identifier for the user (e.g., email address 'user@example.com', username 'johndoe', account ID 'accountid:...', or key for Server/DC)."
        ),
    ],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """
    Retrieve profile information for a specific Jira user.

    Args:
        ctx: The FastMCP context.
        user_identifier: User identifier (email, username, key, or account ID).

    Returns:
        JSON string representing the Jira user profile object, or an error object if not found.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    try:
        user: JiraUser = jira.get_user_profile_by_identifier(user_identifier, jira_pat=jira_pat)
        result = user.to_simplified_dict()
        response_data = {"success": True, "user": result}
    except Exception as e:
        error_message = ""
        log_level = logging.ERROR

        if isinstance(e, ValueError) and "not found" in str(e).lower():
            log_level = logging.WARNING
            error_message = str(e)
        elif isinstance(e, MCPAtlassianAuthenticationError):
            error_message = f"Authentication/Permission Error: {str(e)}"
        elif isinstance(e, OSError | HTTPError):
            error_message = f"Network or API Error: {str(e)}"
        else:
            error_message = (
                "An unexpected error occurred while fetching the user profile."
            )
            logger.exception(
                f"Unexpected error in get_user_profile for '{user_identifier}':"
            )

        error_result = {
            "success": False,
            "error": str(e),
            "user_identifier": user_identifier,
        }
        logger.log(
            log_level,
            f"get_user_profile failed for '{user_identifier}': {error_message}",
        )
        response_data = error_result

    return json.dumps(response_data, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_issue(
    ctx: Context[Any, MainAppContext],
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    fields: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'). "
                "You may also provide a single field as a string (e.g., 'duedate'). "
                "Use '*all' for all fields (including custom fields), or omit for essential fields only."
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    expand: Annotated[
        str | None,
        Field(
            description=(
                "Optional fields to expand. Examples: 'renderedFields' (for rendered content), "
                "'transitions' (for available status transitions), 'changelog' (for history)"
            ),
            default=None,
        ),
    ] = None,
    comment_limit: Annotated[
        int,
        Field(
            description="Maximum number of comments to include (0 or null for no comments)",
            default=10,
            ge=0,
            le=100,
        ),
    ] = 10,
    properties: Annotated[
        str | None,
        Field(
            description="A comma-separated list of issue properties to return",
            default=None,
        ),
    ] = None,
    update_history: Annotated[
        bool,
        Field(
            description="Whether to update the issue view history for the requesting user",
            default=True,
        ),
    ] = True,
) -> str:
    """Get details of a specific Jira issue including its Epic links and relationship information.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        fields: Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'), a single field as a string (e.g., 'duedate'), '*all' for all fields, or omitted for essentials.
        expand: Optional fields to expand.
        comment_limit: Maximum number of comments.
        properties: Issue properties to return.
        update_history: Whether to update issue view history.

    Returns:
        JSON string representing the Jira issue object.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    issue = jira.get_issue(
        issue_key=issue_key,
        fields=fields_list,
        expand=expand,
        comment_limit=comment_limit,
        properties=properties.split(",") if properties else None,
        update_history=update_history,
        jira_pat=jira_pat,
    )
    result = issue.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def search(
    ctx: Context[Any, MainAppContext],
    jql: Annotated[
        str,
        Field(
            description=(
                "JQL query string (Jira Query Language). Examples:\n"
                '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                '- Find issues in Epic: "parent = PROJ-123"\n'
                "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                '- Find by assignee: "assignee = currentUser()"\n'
                '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                '- Find by label: "labels = frontend AND project = PROJ"\n'
                '- Find by priority: "priority = High AND project = PROJ"'
            )
        ),
    ],
    JIRA_PERSONAL_TOKEN: Annotated[str, Field(description="Jira Personal Access Token for this request.")],
    fields: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1),
    ] = 10,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    projects_filter: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated list of project keys to filter results by. "
                "Overrides the environment variable JIRA_PROJECTS_FILTER if provided."
            ),
        ),
    ] = None,
    expand: Annotated[
        str | None,
        Field(
            description=(
                "Optional fields to expand. Examples: 'renderedFields', 'transitions', 'changelog'"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Search Jira issues using JQL (Jira Query Language).

    Args:
        ctx: The FastMCP context.
        jql: JQL query string.
        fields: Comma-separated fields to return.
        limit: Maximum number of results.
        start_at: Starting index for pagination.
        projects_filter: Comma-separated list of project keys to filter by.
        expand: Optional fields to expand.

    Returns:
        JSON string representing the search results including pagination info.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        # Add a more specific error message if the Jira client is not initialized
        error_msg = "Jira client is not initialized in the server lifespan context."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    jira = lifespan_ctx.jira

    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    try:
        search_result = jira.search_issues(
            jql=jql,
            fields=fields_list,
            limit=limit,
            start=start_at,
            expand=expand,
            projects_filter=projects_filter,
        )
        result = search_result.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error in jira_search tool: {e}", exc_info=True)
        raise e


@jira_mcp.tool(tags={"jira", "read"})
async def search_fields(
    ctx: Context[Any, MainAppContext],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    keyword: Annotated[
        str,
        Field(
            description="Keyword for fuzzy search. If left empty, lists the first 'limit' available fields in their default order.",
            default="",
        ),
    ] = "",
    limit: Annotated[
        int, Field(description="Maximum number of results", default=10, ge=1)
    ] = 10,
    refresh: Annotated[
        bool,
        Field(description="Whether to force refresh the field list", default=False),
    ] = False,
) -> str:
    """Search Jira fields by keyword with fuzzy match.

    Args:
        ctx: The FastMCP context.
        keyword: Keyword for fuzzy search.
        limit: Maximum number of results.
        refresh: Whether to force refresh the field list.

    Returns:
        JSON string representing a list of matching field definitions.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    result = jira.search_fields(keyword, limit=limit, refresh=refresh, jira_pat=jira_pat)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_project_issues(
    ctx: Context[Any, MainAppContext],
    project_key: Annotated[str, Field(description="The project key")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
) -> str:
    """Get all issues for a specific Jira project.

    Args:
        ctx: The FastMCP context.
        project_key: The project key.
        limit: Maximum number of results.
        start_at: Starting index for pagination.

    Returns:
        JSON string representing the search results including pagination info.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    search_result = jira.get_project_issues(
        project_key=project_key, start=start_at, limit=limit, jira_pat=jira_pat
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_transitions(
    ctx: Context[Any, MainAppContext],
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """Get available status transitions for a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.

    Returns:
        JSON string representing a list of available transitions.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    # Underlying method returns list[dict] in the desired format
    transitions = jira.get_available_transitions(issue_key, jira_pat=jira_pat)
    return json.dumps(transitions, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_worklog(
    ctx: Context[Any, MainAppContext],
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """Get worklog entries for a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.

    Returns:
        JSON string representing the worklog entries.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    worklogs = jira.get_worklogs(issue_key, jira_pat=jira_pat)
    result = {"worklogs": worklogs}
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def download_attachments(
    ctx: Context[Any, MainAppContext],
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    target_dir: Annotated[
        str, Field(description="Directory where attachments should be saved")
    ],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """Download attachments from a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        target_dir: Directory to save attachments.

    Returns:
        JSON string indicating the result of the download operation.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    result = jira.download_issue_attachments(issue_key=issue_key, target_dir=target_dir, jira_pat=jira_pat)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_agile_boards(
    ctx: Context[Any, MainAppContext],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    board_name: Annotated[
        str | None, Field(description="The name of board, support fuzzy search")
    ] = None,
    project_key: Annotated[
        str | None, Field(description="Jira project key (e.g., 'PROJ-123')")
    ] = None,
    board_type: Annotated[
        str | None,
        Field(description="The type of jira board (e.g., 'scrum', 'kanban')"),
    ] = None,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
) -> str:
    """Get jira agile boards by name, project key, or type.

    Args:
        ctx: The FastMCP context.
        board_name: Name of the board (fuzzy search).
        project_key: Project key.
        board_type: Board type ('scrum' or 'kanban').
        start_at: Starting index.
        limit: Maximum results.

    Returns:
        JSON string representing a list of board objects.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    boards = jira.get_all_agile_boards_model(
        board_name=board_name,
        project_key=project_key,
        board_type=board_type,
        start=start_at,
        limit=limit,
        jira_pat=jira_pat,
    )
    result = [board.to_simplified_dict() for board in boards]
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_board_issues(
    ctx: Context[Any, MainAppContext],
    board_id: Annotated[str, Field(description="The id of the board (e.g., '1001')")],
    jql: Annotated[
        str,
        Field(
            description=(
                "JQL query string (Jira Query Language). Examples:\n"
                '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                '- Find issues in Epic: "parent = PROJ-123"\n'
                "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                '- Find by assignee: "assignee = currentUser()"\n'
                '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                '- Find by label: "labels = frontend AND project = PROJ"\n'
                '- Find by priority: "priority = High AND project = PROJ"'
            )
        ),
    ],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    fields: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual "
                "fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
    expand: Annotated[
        str | None,
        Field(
            description=(
                "Optional fields to expand. Examples: 'renderedFields', 'transitions', 'changelog'"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Get issues for a specific Jira board using JQL.

    Args:
        ctx: The FastMCP context.
        board_id: The ID of the board.
        jql: JQL query string.
        fields: Comma-separated fields to return.
        start_at: Starting index for pagination.
        limit: Maximum number of results.
        expand: Optional fields to expand.

    Returns:
        JSON string representing the search results including pagination info.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    search_result = jira.get_board_issues(
        board_id=board_id,
        jql=jql,
        fields=fields_list,
        start=start_at,
        limit=limit,
        expand=expand,
        jira_pat=jira_pat,
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_sprints_from_board(
    ctx: Context[Any, MainAppContext],
    board_id: Annotated[str, Field(description="The id of the board (e.g., '1001')")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    state: Annotated[
        str | None,
        Field(
            description="State of the sprint ('active', 'closed', 'future'). If omitted, all sprints are returned.",
            default=None,
        ),
    ] = None,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
) -> str:
    """Get sprints for a specific Jira board.

    Args:
        ctx: The FastMCP context.
        board_id: The ID of the board.
        state: State of the sprint ('active', 'closed', 'future').
        start_at: Starting index.
        limit: Maximum results.

    Returns:
        JSON string representing a list of sprint objects.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    sprints = jira.get_sprints_from_board(
        board_id=board_id,
        state=state,
        start=start_at,
        limit=limit,
        jira_pat=jira_pat,
    )
    result = [sprint.to_simplified_dict() for sprint in sprints]
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_sprint_issues(
    ctx: Context[Any, MainAppContext],
    board_id: Annotated[str, Field(description="The id of the board (e.g., '1001')")],
    sprint_id: Annotated[str, Field(description="The id of the sprint (e.g., '123')")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    fields: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual "
                "fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
    expand: Annotated[
        str | None,
        Field(
            description=(
                "Optional fields to expand. Examples: 'renderedFields', 'transitions', 'changelog'"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Get issues for a specific Jira sprint.

    Args:
        ctx: The FastMCP context.
        board_id: The ID of the board.
        sprint_id: The ID of the sprint.
        fields: Comma-separated fields to return.
        start_at: Starting index for pagination.
        limit: Maximum number of results.
        expand: Optional fields to expand.

    Returns:
        JSON string representing the search results including pagination info.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    search_result = jira.get_sprint_issues(
        board_id=board_id,
        sprint_id=sprint_id,
        fields=fields_list,
        start=start_at,
        limit=limit,
        expand=expand,
        jira_pat=jira_pat,
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_link_types(
    ctx: Context[Any, MainAppContext],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """Get all available issue link types in Jira.

    Args:
        ctx: The FastMCP context.

    Returns:
        JSON string representing a list of issue link type objects.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    link_types = jira.get_issue_link_types(jira_pat=jira_pat)
    return json.dumps(link_types, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
async def create_issue(
    ctx: Context[Any, MainAppContext],
    project_key: Annotated[
        str, Field(description="The key of the project to create the issue in")
    ],
    issue_type: Annotated[str, Field(description="The name of the issue type")],
    summary: Annotated[str, Field(description="The summary or title of the issue")],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    description: Annotated[
        str | None, Field(description="The description of the issue", default=None)
    ] = None,
    parent_key: Annotated[
        str | None,
        Field(
            description="The issue key of the parent (e.g., Epic) if creating a sub-task or issue within an Epic",
            default=None,
        ),
    ] = None,
    assignee_id: Annotated[
        str | None,
        Field(
            description="The account ID of the user to assign the issue to",
            default=None,
        ),
    ] = None,
    reporter_id: Annotated[
        str | None,
        Field(
            description="The account ID of the user to set as the reporter",
            default=None,
        ),
    ] = None,
    priority_name: Annotated[
        str | None, Field(description="The name of the priority", default=None)
    ] = None,
    labels: Annotated[
        list[str] | None,
        Field(description="A list of labels to apply to the issue", default=None),
    ] = None,
    due_date: Annotated[
        str | None,
        Field(
            description="The due date of the issue in YYYY-MM-DD format", default=None
        ),
    ] = None,
    custom_fields: Annotated[
        dict[str, Any] | None,
        Field(
            description="A dictionary of custom field IDs or names and their values",
            default=None,
        ),
    ] = None,
) -> str:
    """Create a new Jira issue.

    Args:
        ctx: The FastMCP context.
        project_key: The key of the project.
        issue_type: The name of the issue type.
        summary: The summary or title.
        description: The description.
        parent_key: The issue key of the parent (e.g., Epic).
        assignee_id: The account ID of the assignee.
        reporter_id: The account ID of the reporter.
        priority_name: The name of the priority.
        labels: A list of labels.
        due_date: The due date in YYYY-MM-DD format.
        custom_fields: A dictionary of custom field IDs or names and their values.

    Returns:
        JSON string representing the created issue object.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    try:
        issue = jira.create_issue(
            project_key=project_key,
            issue_type=issue_type,
            summary=summary,
            description=description,
            parent_key=parent_key,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
            priority_name=priority_name,
            labels=labels,
            due_date=due_date,
            custom_fields=custom_fields,
            jira_pat=jira_pat,
        )
        result = issue.to_simplified_dict()
        response_data = {"success": True, "issue": result}
    except Exception as e:
        error_message = f"Failed to create issue: {str(e)}"
        logger.exception(error_message)
        response_data = {"success": False, "error": error_message}

    return json.dumps(response_data, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
async def batch_create_issues(
    ctx: Context[Any, MainAppContext],
    issues: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "A list of dictionaries, where each dictionary represents an issue to be created. "
                "Each issue dictionary should contain fields like 'project_key', 'issue_type', 'summary', etc., "
                "following the structure expected by the create_issue tool."
            )
        ),
    ],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
) -> str:
    """Create multiple Jira issues in a batch.

    Args:
        ctx: The FastMCP context.
        issues: A list of issue dictionaries.

    Returns:
        JSON string representing the results of the batch creation operation.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    try:
        results = jira.batch_create_issues(issues, jira_pat=jira_pat)
        response_data = {"success": True, "results": results}
    except Exception as e:
        error_message = f"Failed to batch create issues: {str(e)}"
        logger.exception(error_message)
        response_data = {"success": False, "error": error_message}

    return json.dumps(response_data, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def batch_get_changelogs(
    ctx: Context[Any, MainAppContext],
    jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)],
    issue_ids_or_keys: Annotated[
        list[str],
        Field(
            description="A list of Jira issue IDs or keys (e.g., ['PROJ-123', '10001'])"
        ),
    ],
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results per issue (1-100)", default=10, ge=1, le=100),
    ] = 10,
) -> str:
    """Get changelog entries for multiple Jira issues in a batch.

    Args:
        ctx: The FastMCP context.
        issue_ids_or_keys: A list of issue IDs or keys.
        start_at: Starting index for pagination.
        limit: Maximum number of results per issue.

    Returns:
        JSON string representing the changelog entries for each issue.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.jira:
        raise ValueError("Jira client is not configured or available.")
    jira = lifespan_ctx.jira

    try:
        changelogs = jira.batch_get_changelogs(
            issue_ids_or_keys=issue_ids_or_keys,
            start_at=start_at,
            limit=limit,
            jira_pat=jira_pat,
        )
        result = {"changelogs": changelogs}
    except Exception as e:
        error_message = f"Failed to get changelogs: {str(e)}"
        logger.exception(error_message)
        result = {"error": error_message}

    return json.dumps(result, indent=2, ensure_ascii=False)
