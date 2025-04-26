import os
from os.path import exists
import json
from collections import defaultdict
from enum import Enum
import itertools
import uuid
from typing import List, Any, Tuple, Dict, Literal
from datetime import datetime, timezone, timedelta
import pandas as pd
from .audio2txt import get_file_path
from .img2txt import process_image
from api.config import (
    sqlite_db_path,
    chat_history_table_name,
    tasks_table_name,
    questions_table_name,
    blocks_table_name,
    tests_table_name,
    cohorts_table_name,
    groups_table_name,
    user_groups_table_name,
    user_cohorts_table_name,
    milestones_table_name,
    tags_table_name,
    task_tags_table_name,
    users_table_name,
    badges_table_name,
    cv_review_usage_table_name,
    organizations_table_name,
    user_organizations_table_name,
    task_scoring_criteria_table_name,
    courses_table_name,
    course_cohorts_table_name,
    course_tasks_table_name,
    uncategorized_milestone_name,
    course_milestones_table_name,
    group_role_learner,
    group_role_mentor,
    uncategorized_milestone_color,
    task_completions_table_name,
    scorecards_table_name,
    question_scorecards_table_name,
    course_generation_jobs_table_name,
    task_generation_jobs_table_name,
)
from api.models import (
    LeaderboardViewType,
    LearningMaterialTask,
    TaskStatus,
    UserCohort,
    StoreMessageRequest,
    ChatMessage,
    TaskAIResponseType,
    QuestionType,
)
from api.utils import (
    get_date_from_str,
    generate_random_color,
    convert_utc_to_ist,
)
from api.utils.url import slugify
from api.utils.db import (
    execute_db_operation,
    get_new_db_connection,
    check_table_exists,
    serialise_list_to_str,
    deserialise_list_from_str,
    execute_multiple_db_operations,
    execute_many_db_operation,
    set_db_defaults,
)
from api.models import TaskType, GenerateCourseJobStatus, GenerateTaskJobStatus


async def create_tests_table(cursor):
    await cursor.execute(
        f"""
            CREATE TABLE IF NOT EXISTS {tests_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                input TEXT NOT NULL,  -- This will store a JSON-encoded list of strings
                output TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE
            )
            """
    )

    await cursor.execute(
        f"""CREATE INDEX idx_test_task_id ON {tests_table_name} (task_id)"""
    )


async def create_organizations_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {organizations_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                default_logo_color TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                openai_api_key TEXT,
                openai_free_trial BOOLEAN
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_org_slug ON {organizations_table_name} (slug)"""
    )


async def create_users_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {users_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                default_dp_color TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""
    )


async def create_user_organizations_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {user_organizations_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                org_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, org_id),
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_org_user_id ON {user_organizations_table_name} (user_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_org_org_id ON {user_organizations_table_name} (org_id)"""
    )


async def create_badges_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {badges_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                image_path TEXT NOT NULL,
                bg_color TEXT NOT NULL,
                cohort_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (cohort_id) REFERENCES {cohorts_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_badge_user_id ON {badges_table_name} (user_id)"""
    )


async def create_cohort_tables(cursor):
    # Create a table to store cohorts
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {cohorts_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                org_id INTEGER NOT NULL,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_cohort_org_id ON {cohorts_table_name} (org_id)"""
    )

    # Create a table to store users in cohorts
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {user_cohorts_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cohort_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                UNIQUE(user_id, cohort_id),
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (cohort_id) REFERENCES {cohorts_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_cohort_user_id ON {user_cohorts_table_name} (user_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_cohort_cohort_id ON {user_cohorts_table_name} (cohort_id)"""
    )

    # Create a table to store groups
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {groups_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cohort_id INTEGER NOT NULL,
                name TEXT,
                FOREIGN KEY (cohort_id) REFERENCES {cohorts_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_group_cohort_id ON {groups_table_name} (cohort_id)"""
    )

    # Create a table to store user groups
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {user_groups_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                UNIQUE(user_id, group_id),
                FOREIGN KEY (group_id) REFERENCES {groups_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_group_user_id ON {user_groups_table_name} (user_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_user_group_group_id ON {user_groups_table_name} (group_id)"""
    )


async def create_course_tasks_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {course_tasks_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                ordering INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                milestone_id INTEGER,
                UNIQUE(task_id, course_id),
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES {courses_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (milestone_id) REFERENCES {milestones_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_task_task_id ON {course_tasks_table_name} (task_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_task_course_id ON {course_tasks_table_name} (course_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_task_milestone_id ON {course_tasks_table_name} (milestone_id)"""
    )


async def create_course_milestones_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {course_milestones_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                milestone_id INTEGER,
                ordering INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(course_id, milestone_id),
                FOREIGN KEY (course_id) REFERENCES {courses_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (milestone_id) REFERENCES {milestones_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_milestone_course_id ON {course_milestones_table_name} (course_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_milestone_milestone_id ON {course_milestones_table_name} (milestone_id)"""
    )


async def create_milestones_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {milestones_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_milestone_org_id ON {milestones_table_name} (org_id)"""
    )


async def create_tag_tables(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {tags_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                org_id INTEGER NOT NULL,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_tag_org_id ON {tags_table_name} (org_id)"""
    )

    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {task_tags_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(task_id, tag_id),
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES {tags_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_tag_task_id ON {task_tags_table_name} (task_id)"""
    )


async def create_courses_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {courses_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_org_id ON {courses_table_name} (org_id)"""
    )


async def create_course_cohorts_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {course_cohorts_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                cohort_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(course_id, cohort_id),
                FOREIGN KEY (course_id) REFERENCES {courses_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (cohort_id) REFERENCES {cohorts_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_cohort_course_id ON {course_cohorts_table_name} (course_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_cohort_cohort_id ON {course_cohorts_table_name} (cohort_id)"""
    )


async def create_tasks_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {tasks_table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    blocks TEXT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    deleted_at DATETIME,
                    scheduled_publish_at DATETIME,
                    FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
                )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_org_id ON {tasks_table_name} (org_id)"""
    )


async def create_questions_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {questions_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                blocks TEXT,
                answer TEXT,
                input_type TEXT NOT NULL,
                coding_language TEXT,
                generation_model TEXT,
                response_type TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME,
                max_attempts INTEGER,
                is_feedback_shown BOOLEAN NOT NULL,
                context TEXT,
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_question_task_id ON {questions_table_name} (task_id)"""
    )


async def create_scorecards_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {scorecards_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                criteria TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES {organizations_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_scorecard_org_id ON {scorecards_table_name} (org_id)"""
    )


async def create_question_scorecards_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {question_scorecards_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                scorecard_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES {questions_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (scorecard_id) REFERENCES {scorecards_table_name}(id) ON DELETE CASCADE,
                UNIQUE(question_id, scorecard_id)
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_question_scorecard_question_id ON {question_scorecards_table_name} (question_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_question_scorecard_scorecard_id ON {question_scorecards_table_name} (scorecard_id)"""
    )


async def create_task_scoring_criteria_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {task_scoring_criteria_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                min_score INTEGER NOT NULL,
                max_score INTEGER NOT NULL,
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_scoring_criteria_task_id ON {task_scoring_criteria_table_name} (task_id)"""
    )


async def create_chat_history_table(cursor):
    await cursor.execute(
        f"""
                CREATE TABLE IF NOT EXISTS {chat_history_table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    response_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES {questions_table_name}(id),
                    FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE
                )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_chat_history_user_id ON {chat_history_table_name} (user_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_chat_history_question_id ON {chat_history_table_name} (question_id)"""
    )


async def create_task_completion_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {task_completions_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER,
                question_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES {questions_table_name}(id) ON DELETE CASCADE,
                UNIQUE(user_id, task_id),
                UNIQUE(user_id, question_id)
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_completion_user_id ON {task_completions_table_name} (user_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_completion_task_id ON {task_completions_table_name} (task_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_completion_question_id ON {task_completions_table_name} (question_id)"""
    )


async def create_cv_review_usage_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {cv_review_usage_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                ai_review TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES {users_table_name}(id) ON DELETE CASCADE
            )
            """
    )


async def create_course_generation_jobs_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {course_generation_jobs_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                job_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES {courses_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_course_generation_job_course_id ON {course_generation_jobs_table_name} (course_id)"""
    )


async def create_task_generation_jobs_table(cursor):
    await cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {task_generation_jobs_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                job_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES {tasks_table_name}(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES {courses_table_name}(id) ON DELETE CASCADE
            )"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_generation_job_task_id ON {task_generation_jobs_table_name} (task_id)"""
    )

    await cursor.execute(
        f"""CREATE INDEX idx_task_generation_job_course_id ON {task_generation_jobs_table_name} (course_id)"""
    )


async def init_db():
    # Ensure the database folder exists
    db_folder = os.path.dirname(sqlite_db_path)
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    if not exists(sqlite_db_path):
        # only set the defaults the first time
        set_db_defaults()

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        if exists(sqlite_db_path):
            if not await check_table_exists(organizations_table_name, cursor):
                await create_organizations_table(cursor)

            if not await check_table_exists(users_table_name, cursor):
                await create_users_table(cursor)

            if not await check_table_exists(user_organizations_table_name, cursor):
                await create_user_organizations_table(cursor)

            if not await check_table_exists(cohorts_table_name, cursor):
                await create_cohort_tables(cursor)

            if not await check_table_exists(courses_table_name, cursor):
                await create_courses_table(cursor)

            if not await check_table_exists(course_cohorts_table_name, cursor):
                await create_course_cohorts_table(cursor)

            if not await check_table_exists(milestones_table_name, cursor):
                await create_milestones_table(cursor)

            if not await check_table_exists(tags_table_name, cursor):
                await create_tag_tables(cursor)

            if not await check_table_exists(badges_table_name, cursor):
                await create_badges_table(cursor)

            if not await check_table_exists(tasks_table_name, cursor):
                await create_tasks_table(cursor)

            if not await check_table_exists(questions_table_name, cursor):
                await create_questions_table(cursor)

            if not await check_table_exists(scorecards_table_name, cursor):
                await create_scorecards_table(cursor)

            if not await check_table_exists(question_scorecards_table_name, cursor):
                await create_question_scorecards_table(cursor)

            if not await check_table_exists(task_scoring_criteria_table_name, cursor):
                await create_task_scoring_criteria_table(cursor)

            if not await check_table_exists(tests_table_name, cursor):
                await create_tests_table(cursor)

            if not await check_table_exists(chat_history_table_name, cursor):
                await create_chat_history_table(cursor)

            if not await check_table_exists(task_completions_table_name, cursor):
                await create_task_completion_table(cursor)

            if not await check_table_exists(course_tasks_table_name, cursor):
                await create_course_tasks_table(cursor)

            if not await check_table_exists(course_milestones_table_name, cursor):
                await create_course_milestones_table(cursor)

            if not await check_table_exists(cv_review_usage_table_name, cursor):
                await create_cv_review_usage_table(cursor)

            if not await check_table_exists(course_generation_jobs_table_name, cursor):
                await create_course_generation_jobs_table(cursor)

            if not await check_table_exists(task_generation_jobs_table_name, cursor):
                await create_task_generation_jobs_table(cursor)

            await conn.commit()
            return

        try:
            await create_organizations_table(cursor)

            await create_users_table(cursor)

            await create_user_organizations_table(cursor)

            await create_milestones_table(cursor)

            await create_tag_tables(cursor)

            await create_cohort_tables(cursor)

            await create_courses_table(cursor)

            await create_course_cohorts_table(cursor)

            await create_badges_table(cursor)

            await create_tasks_table(cursor)

            await create_questions_table(cursor)

            await create_scorecards_table(cursor)

            await create_question_scorecards_table(cursor)

            await create_task_scoring_criteria_table(cursor)

            await create_chat_history_table(cursor)

            await create_task_completion_table(cursor)

            await create_tests_table(cursor)

            await create_course_tasks_table(cursor)

            await create_course_milestones_table(cursor)

            await create_cv_review_usage_table(cursor)

            await create_course_generation_jobs_table(cursor)

            await create_task_generation_jobs_table(cursor)

            await conn.commit()

        except Exception as exception:
            # delete db
            os.remove(sqlite_db_path)
            raise exception


async def add_tags_to_task(task_id: int, tag_ids_to_add: List):
    if not tag_ids_to_add:
        return

    await execute_many_db_operation(
        f"INSERT INTO {task_tags_table_name} (task_id, tag_id) VALUES (?, ?)",
        [(task_id, tag_id) for tag_id in tag_ids_to_add],
    )


async def remove_tags_from_task(task_id: int, tag_ids_to_remove: List):
    if not tag_ids_to_remove:
        return

    await execute_db_operation(
        f"DELETE FROM {task_tags_table_name} WHERE task_id = ? AND tag_id IN ({','.join(map(str, tag_ids_to_remove))})",
        (task_id,),
    )


async def get_org_id_for_course(course_id: int):
    course = await execute_db_operation(
        f"SELECT org_id FROM {courses_table_name} WHERE id = ?",
        (course_id,),
        fetch_one=True,
    )

    if not course:
        raise ValueError("Course not found")

    return course[0]


async def create_draft_task_for_course(
    title: str,
    type: str,
    course_id: int,
    milestone_id: int,
) -> Tuple[int, int]:
    org_id = await get_org_id_for_course(course_id)

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        query = f"INSERT INTO {tasks_table_name} (org_id, type, title, status) VALUES (?, ?, ?, ?)"

        await cursor.execute(
            query,
            (org_id, str(type), title, "draft"),
        )

        task_id = cursor.lastrowid

        # Get the maximum ordering value for this milestone
        await cursor.execute(
            f"SELECT COALESCE(MAX(ordering), -1) FROM {course_tasks_table_name} WHERE course_id = ? AND milestone_id = ?",
            (course_id, milestone_id),
        )
        max_ordering = await cursor.fetchone()

        # Set the new milestone's order to be the next value
        next_ordering = max_ordering[0] + 1 if max_ordering else 0

        await cursor.execute(
            f"INSERT INTO {course_tasks_table_name} (course_id, task_id, milestone_id, ordering) VALUES (?, ?, ?, ?)",
            (course_id, task_id, milestone_id, next_ordering),
        )

        await conn.commit()

        return task_id, next_ordering


def return_test_rows_as_dict(test_rows: List[Tuple[str, str, str]]) -> List[Dict]:
    return [
        {"input": json.loads(row[0]), "output": row[1], "description": row[2]}
        for row in test_rows
    ]


async def get_all_learning_material_tasks_for_course(course_id: int):
    query = f"""
    SELECT t.id, t.title, t.type, t.status
    FROM {tasks_table_name} t
    INNER JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
    WHERE ct.course_id = ? AND t.deleted_at IS NULL AND t.type = '{TaskType.LEARNING_MATERIAL}' AND t.status = '{TaskStatus.PUBLISHED}'
    ORDER BY ct.ordering ASC
    """

    query_params = (course_id,)

    tasks = await execute_db_operation(query, query_params, fetch_all=True)

    return [
        {"id": task[0], "title": task[1], "type": task[2], "status": task[3]}
        for task in tasks
    ]


async def fetch_blocks(owner_id: int, owner_type: Literal["task", "question"]):
    owner_id_param = "task_id" if owner_type == "task" else "question_id"

    # Fetch blocks for this task
    blocks_data = await execute_db_operation(
        f"""
        SELECT id, parent_id, type, properties, content, position
        FROM {blocks_table_name}
        WHERE {owner_id_param} = ?
        ORDER BY CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END, parent_id, position
        """,
        (owner_id,),
        fetch_all=True,
    )

    # Convert blocks to a tree structure
    block_tree = []
    block_dict = {}

    if not blocks_data:
        return []

    # Create a dictionary of all blocks
    for block_row in blocks_data:
        block_id, parent_id, block_type, properties_json, content, position = block_row

        # Parse properties from JSON
        try:
            properties = json.loads(properties_json)
            if not properties:
                properties = {}
        except:
            properties = {}

        # Extract client ID if it exists
        client_id = properties.pop("client_id", None)

        # Parse content based on block type
        block_content = content
        if content:
            try:
                # Try to parse as JSON first
                parsed_content = json.loads(content)
                block_content = parsed_content
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, keep as is
                pass

        block = {
            "id": client_id
            or str(block_id),  # Use client ID if available, otherwise use DB ID
            "type": block_type,
            "props": properties,
            "content": block_content,
            "position": position,
            "children": [],
        }

        block_dict[block_id] = block

        # Add to tree if it's a root block
        if parent_id is None:
            block_tree.append(block)

    # Link children to parents
    for block_row in blocks_data:
        block_id, parent_id, _, _, _, _ = block_row
        if parent_id is not None and parent_id in block_dict:
            block_dict[parent_id]["children"].append(block_dict[block_id])

    return block_tree


def convert_question_db_to_dict(question) -> Dict:
    return {
        "id": question[0],
        "type": question[1],
        "blocks": json.loads(question[2]) if question[2] else [],
        "answer": json.loads(question[3]) if question[3] else None,
        "input_type": question[4],
        "response_type": question[5],
        "scorecard_id": question[6],
        "context": json.loads(question[7]) if question[7] else None,
        "coding_languages": json.loads(question[8]) if question[8] else None,
    }


async def get_scorecard(scorecard_id: int) -> Dict:
    scorecard = await execute_db_operation(
        f"SELECT id, title, criteria FROM {scorecards_table_name} WHERE id = ?",
        (scorecard_id,),
        fetch_one=True,
    )

    if not scorecard:
        return None

    return {
        "id": scorecard[0],
        "title": scorecard[1],
        "criteria": json.loads(scorecard[2]),
    }


async def get_question(question_id: int) -> Dict:
    question = await execute_db_operation(
        f"""
        SELECT q.id, q.type, q.blocks, q.answer, q.input_type, q.response_type, qs.scorecard_id, q.context, q.coding_language
        FROM {questions_table_name} q
        LEFT JOIN {question_scorecards_table_name} qs ON q.id = qs.question_id
        WHERE q.id = ?
        """,
        (question_id,),
        fetch_one=True,
    )

    if not question:
        return None

    question = convert_question_db_to_dict(question)

    if question["scorecard_id"] is not None:
        question["scorecard"] = await get_scorecard(question["scorecard_id"])

    return question


def construct_description_from_blocks(
    blocks: List[Dict], nesting_level: int = 0
) -> str:
    """
    Constructs a textual description from a tree of block data.

    Args:
        blocks: A list of block dictionaries, potentially with nested children
        nesting_level: The current nesting level (used for proper indentation)

    Returns:
        A formatted string representing the content of the blocks
    """
    if not blocks:
        return ""

    description = ""
    indent = "    " * nesting_level  # 4 spaces per nesting level

    for block in blocks:
        block_type = block.get("type", "")
        content = block.get("content", [])
        children = block.get("children", [])

        if block_type == "paragraph":
            if isinstance(content, list):
                paragraph_text = ""
                for text_obj in content:
                    if isinstance(text_obj, dict) and "text" in text_obj:
                        paragraph_text += text_obj["text"]
                if paragraph_text:
                    description += f"{indent}{paragraph_text}\n"

        elif block_type == "image":
            explain = block.get("props", {}).get("explain", "")
            img_url = block.get("props", {}).get("url", "")
            description += f"{indent}# Image File\n"
            description += f"{indent}[Image file attached: {img_url}]\n\n"
            description += f"{indent}Brief description of the image:\n{indent}{explain}\n"
            print("Pranav image:", explain)

        elif block_type == "audio":
            explain = block.get("props", {}).get("explain", "")
            aud_url = block.get("props", {}).get("url", "")
            description += f"{indent}# Audio File\n"
            description += f"{indent}[Audio file attached: {aud_url}]\n\n"
            description += f"{indent}Brief description or transcript of the audio:\n{indent}{explain}\n"
            print("Pranav audio:", explain)

        elif block_type == "heading":
            level = block.get("props", {}).get("level", 1)
            if isinstance(content, list):
                heading_text = ""
                for text_obj in content:
                    if isinstance(text_obj, dict) and "text" in text_obj:
                        heading_text += text_obj["text"]
                if heading_text:
                    description += f"{indent}{'#' * level} {heading_text}\n"

        elif block_type == "codeBlock":
            language = block.get("props", {}).get("language", "")
            if isinstance(content, list):
                code_text = ""
                for text_obj in content:
                    if isinstance(text_obj, dict) and "text" in text_obj:
                        code_text += text_obj["text"]
                if code_text:
                    description += f"{indent}```{language}\n{indent}{code_text}\n{indent}```\n"

        elif block_type in ["numberedListItem", "checkListItem", "bulletListItem"]:
            if isinstance(content, list):
                item_text = ""
                for text_obj in content:
                    if isinstance(text_obj, dict) and "text" in text_obj:
                        item_text += text_obj["text"]
                if item_text:
                    if block_type == "numberedListItem":
                        marker = "1. "
                    elif block_type == "checkListItem":
                        marker = "- [ ] "
                    elif block_type == "bulletListItem":
                        marker = "- "
                    description += f"{indent}{marker}{item_text}\n"

        if children:
            child_description = construct_description_from_blocks(
                children, nesting_level + 1
            )
            description += child_description

    return description

async def get_basic_task_details(task_id: int) -> Dict:
    task = await execute_db_operation(
        f"""
        SELECT id, title, type, status, org_id, scheduled_publish_at
        FROM {tasks_table_name}
        WHERE id = ? AND deleted_at IS NULL
        """,
        (task_id,),
        fetch_one=True,
    )

    if not task:
        return None

    return {
        "id": task[0],
        "title": task[1],
        "type": task[2],
        "status": task[3],
        "org_id": task[4],
        "scheduled_publish_at": task[5],
    }


async def get_task(task_id: int):
    task_data = await get_basic_task_details(task_id)

    if not task_data:
        return None

    if task_data["type"] == TaskType.LEARNING_MATERIAL:
        result = await execute_db_operation(
            f"SELECT blocks FROM {tasks_table_name} WHERE id = ?",
            (task_id,),
            fetch_one=True,
        )

        task_data["blocks"] = json.loads(result[0]) if result[0] else []

    elif task_data["type"] in [TaskType.QUIZ, TaskType.EXAM]:
        questions = await execute_db_operation(
            f"""
            SELECT q.id, q.type, q.blocks, q.answer, q.input_type, q.response_type, qs.scorecard_id, q.context, q.coding_language
            FROM {questions_table_name} q
            LEFT JOIN {question_scorecards_table_name} qs ON q.id = qs.question_id
            WHERE task_id = ? ORDER BY position ASC
            """,
            (task_id,),
            fetch_all=True,
        )

        task_data["questions"] = [
            convert_question_db_to_dict(question) for question in questions
        ]

    return task_data


async def does_task_exist(task_id: int) -> bool:
    task = await execute_db_operation(
        f"""
        SELECT id
        FROM {tasks_table_name}
        WHERE id = ? AND deleted_at IS NULL
        """,
        (task_id,),
        fetch_one=True,
    )

    return task is not None


def prepare_blocks_for_publish(blocks: List[Dict]) -> List[Dict]:
    for index, block in enumerate(blocks):
        if "id" not in block or block["id"] is None:
            block["id"] = str(uuid.uuid4())

        block["position"] = index

    return blocks

def media_block(blocks: List[Dict])-> List[Dict]:
    for block in blocks:
        block_type = block.get("type", "")
        content = block.get("content", [])
        children = block.get("children", [])

        if block_type == "image":
            img_url = block["props"]["url"]
            summary_of_image = process_image(img_url)
            # Directly add 'explain' field to the block's props
            block["props"]["explain"] = summary_of_image
            print("Pranav image:", summary_of_image)
        
        elif block_type == "audio":
            aud_url = block["props"]["url"]
            x=get_file_path(aud_url)
            block["props"]["explain"] = x
            print("Pranav audio:", x)
    return blocks



async def publish_learning_material_task(
    task_id: int,
    title: str,
    blocks: List[Dict],
    scheduled_publish_at: datetime,
    status: TaskStatus = TaskStatus.PUBLISHED,
) -> LearningMaterialTask:
    if not await does_task_exist(task_id):
        return False

    # Execute all operations in a single transaction
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()
        
        media_block(blocks)
        print("Pranav Block:",blocks)

        await cursor.execute(
            f"UPDATE {tasks_table_name} SET blocks = ?, status = ?, title = ?, scheduled_publish_at = ? WHERE id = ?",
            (
                json.dumps(prepare_blocks_for_publish(blocks)),
                str(status),
                title,
                scheduled_publish_at,
                task_id,
            ),
        )

        await conn.commit()

        return await get_task(task_id)


async def publish_quiz(
    task_id: int,
    title: str,
    questions: List[Dict],
    scheduled_publish_at: datetime,
    status: TaskStatus = TaskStatus.PUBLISHED,
):
    if not await does_task_exist(task_id):
        return False

    task = await get_basic_task_details(task_id)

    if not task:
        return False

    org_id = task["org_id"]

    scorecard_uuid_to_id = {}

    # Execute all operations in a single transaction
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                question = question.model_dump()

            await cursor.execute(
                f"""
                INSERT INTO {questions_table_name} (task_id, type, blocks, answer, input_type, response_type, coding_language, generation_model, context, position, max_attempts, is_feedback_shown) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    str(question["type"]),
                    json.dumps(prepare_blocks_for_publish(question["blocks"])),
                    (
                        json.dumps(prepare_blocks_for_publish(question["answer"]))
                        if question["answer"]
                        else None
                    ),
                    str(question["input_type"]),
                    str(question["response_type"]),
                    (
                        json.dumps(question["coding_languages"])
                        if question["coding_languages"]
                        else None
                    ),
                    str(question["generation_model"]),
                    json.dumps(question["context"]) if question["context"] else None,
                    index,
                    question["max_attempts"],
                    question["is_feedback_shown"],
                ),
            )

            question_id = cursor.lastrowid

            scorecard_id = None
            if question["scorecard_id"] is not None:
                scorecard_id = question["scorecard_id"]
            elif question["scorecard"]:
                if question["scorecard"]["id"] not in scorecard_uuid_to_id:
                    await cursor.execute(
                        f"""
                        INSERT INTO {scorecards_table_name} (org_id, title, criteria) VALUES (?, ?, ?)
                        """,
                        (
                            org_id,
                            question["scorecard"]["title"],
                            json.dumps(question["scorecard"]["criteria"]),
                        ),
                    )

                    scorecard_id = cursor.lastrowid
                    scorecard_uuid_to_id[question["scorecard"]["id"]] = scorecard_id
                else:
                    scorecard_id = scorecard_uuid_to_id[question["scorecard"]["id"]]

            if scorecard_id is not None:
                await cursor.execute(
                    f"""
                    INSERT INTO {question_scorecards_table_name} (question_id, scorecard_id) VALUES (?, ?)
                    """,
                    (question_id, scorecard_id),
                )

        # Update task status to published
        await cursor.execute(
            f"UPDATE {tasks_table_name} SET status = ?, title = ?, scheduled_publish_at = ? WHERE id = ?",
            (str(status), title, scheduled_publish_at, task_id),
        )

        await conn.commit()

        return await get_task(task_id)


async def update_quiz(
    task_id: int, title: str, questions: List[Dict], scheduled_publish_at: datetime
):
    if not await does_task_exist(task_id):
        return False

    # Execute all operations in a single transaction
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()
        for question in questions:
            question = question.model_dump()

            await cursor.execute(
                f"""
                UPDATE {questions_table_name} SET blocks = ?, answer = ?, input_type = ?, coding_language = ?, context = ? WHERE id = ?
                """,
                (
                    json.dumps(prepare_blocks_for_publish(question["blocks"])),
                    (
                        json.dumps(prepare_blocks_for_publish(question["answer"]))
                        if question["answer"]
                        else None
                    ),
                    str(question["input_type"]),
                    (
                        json.dumps(question["coding_languages"])
                        if question["coding_languages"]
                        else None
                    ),
                    json.dumps(question["context"]) if question["context"] else None,
                    question["id"],
                ),
            )

        # Update task status to published
        await cursor.execute(
            f"UPDATE {tasks_table_name} SET title = ?, scheduled_publish_at = ? WHERE id = ?",
            (title, scheduled_publish_at, task_id),
        )

        await conn.commit()

        return await get_task(task_id)


async def get_scoring_criteria_for_task(task_id: int):
    rows = await execute_db_operation(
        f"SELECT id, category, description, min_score, max_score FROM {task_scoring_criteria_table_name} WHERE task_id = ?",
        (task_id,),
        fetch_all=True,
    )

    return [
        {
            "id": row[0],
            "category": row[1],
            "description": row[2],
            "range": [row[3], row[4]],
        }
        for row in rows
    ]


async def get_scoring_criteria_for_tasks(task_ids: List[int]):
    rows = await execute_db_operation(
        f"""
        SELECT id, category, description, min_score, max_score, task_id 
        FROM {task_scoring_criteria_table_name} 
        WHERE task_id IN ({','.join(map(str, task_ids))})
        """,
        fetch_all=True,
    )

    # Group scoring criteria by task_id
    criteria_by_task = {}
    for row in rows:
        task_id = row[5]

        if task_id not in criteria_by_task:
            criteria_by_task[task_id] = []

        criteria_by_task[task_id].append(
            {
                "id": row[0],
                "category": row[1],
                "description": row[2],
                "range": [row[3], row[4]],
            }
        )

    # Return criteria in same order as input task_ids
    return [criteria_by_task.get(task_id, []) for task_id in task_ids]


async def delete_task(task_id: int):
    await execute_db_operation(
        f"""
        UPDATE {tasks_table_name} SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL
        """,
        (datetime.now(), task_id),
    )


async def delete_tasks(task_ids: List[int]):
    task_ids_as_str = serialise_list_to_str(map(str, task_ids))

    await execute_db_operation(
        f"""
        UPDATE {tasks_table_name} SET deleted_at = ? WHERE id IN ({task_ids_as_str}) AND deleted_at IS NULL
        """,
        (datetime.now(),),
    )


async def store_messages(
    messages: List[StoreMessageRequest],
    user_id: int,
    question_id: int,
    is_complete: bool,
):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        new_row_ids = []

        for message in messages:
            # Insert the new message
            await cursor.execute(
                f"""
            INSERT INTO {chat_history_table_name} (user_id, question_id, role, content, response_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    question_id,
                    message.role,
                    message.content,
                    message.response_type,
                    message.created_at,
                ),
            )

            new_row_id = cursor.lastrowid
            new_row_ids.append(new_row_id)

        if is_complete:
            await cursor.execute(
                f"""
                INSERT INTO {task_completions_table_name} (user_id, question_id)
                VALUES (?, ?) ON CONFLICT(user_id, question_id) DO NOTHING
                """,
                (user_id, question_id),
            )

        await conn.commit()

    # Fetch the newly inserted row
    new_rows = await execute_db_operation(
        f"""SELECT id, created_at, user_id, question_id, role, content, response_type
    FROM {chat_history_table_name}
    WHERE id IN ({','.join(map(str, new_row_ids))})
    """,
        fetch_all=True,
    )

    # Return the newly inserted row as a dictionary
    return [
        {
            "id": new_row[0],
            "created_at": new_row[1],
            "user_id": new_row[2],
            "question_id": new_row[3],
            "role": new_row[4],
            "content": new_row[5],
            "response_type": new_row[6],
        }
        for new_row in new_rows
    ]


async def get_all_chat_history(org_id: int):
    chat_history = await execute_db_operation(
        f"""
        SELECT message.id, message.created_at, user.id AS user_id, user.email AS user_email, message.question_id, task.id AS task_id, message.role, message.content, message.response_type
        FROM {chat_history_table_name} message
        INNER JOIN {questions_table_name} question ON message.question_id = question.id
        INNER JOIN {tasks_table_name} task ON question.task_id = task.id
        INNER JOIN {users_table_name} user ON message.user_id = user.id 
        WHERE task.deleted_at IS NULL AND task.org_id = ?
        ORDER BY message.created_at ASC
        """,
        (org_id,),
        fetch_all=True,
    )

    return [
        {
            "id": row[0],
            "created_at": row[1],
            "user_id": row[2],
            "user_email": row[3],
            "question_id": row[4],
            "task_id": row[5],
            "role": row[6],
            "content": row[7],
            "response_type": row[8],
        }
        for row in chat_history
    ]


def convert_chat_message_to_dict(message: Tuple) -> ChatMessage:
    return {
        "id": message[0],
        "created_at": message[1],
        "user_id": message[2],
        "question_id": message[3],
        "role": message[4],
        "content": message[5],
        "response_type": message[6],
    }


async def get_question_chat_history_for_user(
    question_id: int, user_id: int
) -> List[ChatMessage]:
    chat_history = await execute_db_operation(
        f"""
    SELECT id, created_at, user_id, question_id, role, content, response_type FROM {chat_history_table_name} WHERE question_id = ? AND user_id = ?
    """,
        (question_id, user_id),
        fetch_all=True,
    )

    return [convert_chat_message_to_dict(row) for row in chat_history]


async def get_task_chat_history_for_user(
    task_id: int, user_id: int
) -> List[ChatMessage]:
    task = await get_basic_task_details(task_id)

    if not task:
        raise ValueError("Task does not exist")

    if task["type"] == TaskType.LEARNING_MATERIAL:
        raise ValueError("Task is not a quiz or exam")

    query = f"""
        SELECT ch.id, ch.created_at, ch.user_id, ch.question_id, ch.role, ch.content, ch.response_type
        FROM {chat_history_table_name} ch
        JOIN {questions_table_name} q ON ch.question_id = q.id
        WHERE q.task_id = ? 
        AND ch.user_id = ?
        ORDER BY ch.created_at ASC
    """

    chat_history = await execute_db_operation(
        query,
        (task_id, user_id),
        fetch_all=True,
    )

    return [convert_chat_message_to_dict(row) for row in chat_history]


async def get_solved_tasks_for_user(
    user_id: int,
    cohort_id: int,
    view_type: LeaderboardViewType = LeaderboardViewType.ALL_TIME,
):
    if view_type == LeaderboardViewType.ALL_TIME:
        results = await execute_db_operation(
            f"""
        SELECT DISTINCT ch.task_id 
        FROM {chat_history_table_name} ch
        JOIN {tasks_table_name} t ON t.id = ch.task_id
        JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
        JOIN {course_cohorts_table_name} cc ON ct.course_id = cc.course_id
        WHERE ch.user_id = ? AND ch.is_solved = 1 AND cc.cohort_id = ? AND t.deleted_at IS NULL
        """,
            (user_id, cohort_id),
            fetch_all=True,
        )
    else:
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        if view_type == LeaderboardViewType.WEEKLY:
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # MONTHLY
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        results = await execute_db_operation(
            f"""
        WITH FirstSolved AS (
            SELECT ch.task_id, MIN(datetime(ch.timestamp, '+5 hours', '+30 minutes')) as first_solved_time
            FROM {chat_history_table_name} ch
            JOIN {tasks_table_name} t ON t.id = ch.task_id
            JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
            JOIN {course_cohorts_table_name} cc ON ct.course_id = cc.course_id
            WHERE ch.user_id = ? AND ch.is_solved = 1 AND cc.cohort_id = ? AND t.deleted_at IS NULL
            GROUP BY ch.task_id
        )
        SELECT DISTINCT task_id 
        FROM FirstSolved
        WHERE first_solved_time >= ?
        """,
            (user_id, cohort_id, start_date),
            fetch_all=True,
        )

    return [task[0] for task in results]


async def mark_task_completed(task_id: int, user_id: int):
    # Update task completion table
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Check if the task is already marked as completed
        existing_completion = await execute_db_operation(
            f"""
            SELECT id FROM {task_completions_table_name}
            WHERE user_id = ? AND task_id = ?
            """,
            (user_id, task_id),
            fetch_one=True,
        )
        if existing_completion:
            return

        # If not already completed, insert a new record
        await cursor.execute(
            f"""
            INSERT INTO {task_completions_table_name} (user_id, task_id)
            VALUES (?, ?)
            """,
            (user_id, task_id),
        )

        await conn.commit()


async def get_cohort_completion(
    cohort_id: int, user_ids: List[int], course_id: int = None
):
    """
    Retrieves completion data for a user in a specific cohort.

    Args:
        cohort_id: The ID of the cohort
        user_ids: The IDs of the users
        course_id: The ID of the course (optional, if not provided, all courses in the cohort will be considered)

    Returns:
        A dictionary mapping task IDs to their completion status:
        {
            task_id: {
                "is_complete": bool,
                "questions": [{"question_id": int, "is_complete": bool}]
            }
        }
    """
    results = defaultdict(dict)

    # user_in_cohort = await is_user_in_cohort(user_id, cohort_id)
    # if not user_in_cohort:
    #     results[user_id] = {}
    #     continue

    # Get completed tasks for the users from task_completions_table
    completed_tasks = await execute_db_operation(
        f"""
        SELECT user_id, task_id 
        FROM {task_completions_table_name}
        WHERE user_id in ({','.join(map(str, user_ids))}) AND task_id IS NOT NULL
        """,
        fetch_all=True,
    )
    completed_task_ids_for_user = defaultdict(set)
    for user_id, task_id in completed_tasks:
        completed_task_ids_for_user[user_id].add(task_id)

    # Get completed questions for the users from task_completions_table
    completed_questions = await execute_db_operation(
        f"""
        SELECT user_id, question_id 
        FROM {task_completions_table_name}
        WHERE user_id in ({','.join(map(str, user_ids))}) AND question_id IS NOT NULL
        """,
        fetch_all=True,
    )
    completed_question_ids_for_user = defaultdict(set)
    for user_id, question_id in completed_questions:
        completed_question_ids_for_user[user_id].add(question_id)

    # Get all tasks for the cohort
    # Get learning material tasks
    query = f"""
        SELECT DISTINCT t.id
        FROM {tasks_table_name} t
        JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
        JOIN {course_cohorts_table_name} cc ON ct.course_id = cc.course_id
        WHERE cc.cohort_id = ? AND t.deleted_at IS NULL AND t.type = '{TaskType.LEARNING_MATERIAL}' AND t.status = '{TaskStatus.PUBLISHED}' AND t.scheduled_publish_at IS NULL
        """
    params = (cohort_id,)

    if course_id is not None:
        query += " AND ct.course_id = ?"
        params += (course_id,)

    learning_material_tasks = await execute_db_operation(
        query,
        params,
        fetch_all=True,
    )

    for user_id in user_ids:
        for task in learning_material_tasks:
            # For learning material, check if it's in the completed tasks list
            results[user_id][task[0]] = {
                "is_complete": task[0] in completed_task_ids_for_user[user_id]
            }

    # Get quiz and exam task questions
    query = f"""
        SELECT DISTINCT t.id as task_id, q.id as question_id
        FROM {tasks_table_name} t
        JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
        JOIN {course_cohorts_table_name} cc ON ct.course_id = cc.course_id
        LEFT JOIN {questions_table_name} q ON t.id = q.task_id AND q.deleted_at IS NULL
        WHERE cc.cohort_id = ? AND t.deleted_at IS NULL AND t.type IN ('{TaskType.QUIZ}', '{TaskType.EXAM}') AND t.status = '{TaskStatus.PUBLISHED}' AND t.scheduled_publish_at IS NULL{
            " AND ct.course_id = ?" if course_id else ""
        } 
        ORDER BY t.id, q.position ASC
        """
    params = (cohort_id,)

    if course_id is not None:
        params += (course_id,)

    quiz_exam_questions = await execute_db_operation(
        query,
        params,
        fetch_all=True,
    )

    # Group questions by task_id
    quiz_exam_tasks = defaultdict(list)
    for row in quiz_exam_questions:
        task_id = row[0]
        question_id = row[1]

        quiz_exam_tasks[task_id].append(question_id)

    for user_id in user_ids:
        for task_id in quiz_exam_tasks:
            is_task_complete = True
            question_completions = []

            for question_id in quiz_exam_tasks[task_id]:
                is_question_complete = (
                    question_id in completed_question_ids_for_user[user_id]
                )

                question_completions.append(
                    {
                        "question_id": question_id,
                        "is_complete": is_question_complete,
                    }
                )

                if not is_question_complete:
                    is_task_complete = False

            results[user_id][task_id] = {
                "is_complete": is_task_complete,
                "questions": question_completions,
            }

    return results


async def get_cohort_course_attempt_data(cohort_learner_ids: List[int], course_id: int):
    """
    Retrieves attempt data for users in a specific cohort, focusing on whether each user
    has attempted any task from each course assigned to the cohort.

    An attempt is defined as either:
    1. Having at least one entry in task_completions_table for a learning material task in the course
    2. Having at least one message in chat_history_table for a question in a quiz/exam task in the course

    Args:
        cohort_learner_ids: The IDs of the learners in the cohort
        course_id: The ID of the course to check

    Returns:
        A dictionary with the following structure:
        {
            user_id: {
                course_id: {
                    "course_name": str,
                    "has_attempted": bool,
                    "last_attempt_date": str or None,
                    "attempt_count": int
                }
            }
        }
    """
    result = defaultdict(dict)

    # Initialize result structure with all courses for all users
    for user_id in cohort_learner_ids:
        result[user_id][course_id] = {
            "has_attempted": False,
        }

    cohort_learner_ids_str = ",".join(map(str, cohort_learner_ids))

    # Get all learning material tasks attempted for this course
    task_completions = await execute_db_operation(
        f"""
        SELECT DISTINCT tc.user_id
        FROM {task_completions_table_name} tc
        JOIN {course_tasks_table_name} ct ON tc.task_id = ct.task_id
        WHERE tc.user_id IN ({cohort_learner_ids_str}) AND ct.course_id = ?
        ORDER BY tc.created_at ASC
        """,
        (course_id,),
        fetch_all=True,
    )

    # Process task completion data
    for completion in task_completions:
        user_id = completion[0]
        result[user_id][course_id]["has_attempted"] = True

    chat_messages = await execute_db_operation(
        f"""
        SELECT DISTINCT ch.user_id
        FROM {chat_history_table_name} ch
        JOIN {questions_table_name} q ON ch.question_id = q.id
        JOIN {tasks_table_name} t ON q.task_id = t.id
        JOIN {course_tasks_table_name} ct ON t.id = ct.task_id
        WHERE ch.user_id IN ({cohort_learner_ids_str}) AND ct.course_id = ?
        GROUP BY ch.user_id
        """,
        (course_id,),
        fetch_all=True,
    )

    # Process chat message data
    for message_data in chat_messages:
        user_id = message_data[0]
        result[user_id][course_id]["has_attempted"] = True

    # Convert defaultdict to regular dict for cleaner response
    return {user_id: dict(courses) for user_id, courses in result.items()}


async def delete_message(message_id: int):
    await execute_db_operation(
        f"DELETE FROM {chat_history_table_name} WHERE id = ?", (message_id,)
    )


async def update_message_timestamp(message_id: int, new_timestamp: datetime):
    await execute_db_operation(
        f"UPDATE {chat_history_table_name} SET timestamp = ? WHERE id = ?",
        (new_timestamp, message_id),
    )


async def delete_user_chat_history_for_task(question_id: int, user_id: int):
    await execute_db_operation(
        f"DELETE FROM {chat_history_table_name} WHERE question_id = ? AND user_id = ?",
        (question_id, user_id),
    )


async def delete_completion_history_for_task(
    task_id: int, question_id: int, user_id: int
):
    if task_id is not None:
        await execute_db_operation(
            f"DELETE FROM {chat_history_table_name} WHERE task_id = ? AND user_id = ?",
            (task_id, user_id),
        )

    await execute_db_operation(
        f"DELETE FROM {chat_history_table_name} WHERE question_id = ? AND user_id = ?",
        (question_id, user_id),
    )


async def delete_all_chat_history():
    await execute_db_operation(f"DELETE FROM {chat_history_table_name}")


async def get_user_active_in_last_n_days(user_id: int, n: int, cohort_id: int):
    activity_per_day = await execute_db_operation(
        f"""
    WITH chat_activity AS (
        SELECT DATE(datetime(created_at, '+5 hours', '+30 minutes')) as activity_date, COUNT(*) as count
        FROM {chat_history_table_name}
        WHERE user_id = ? 
        AND DATE(datetime(created_at, '+5 hours', '+30 minutes')) >= DATE(datetime('now', '+5 hours', '+30 minutes'), '-{n} days') 
        AND question_id IN (
            SELECT question_id 
            FROM {questions_table_name} 
            WHERE task_id IN (
                SELECT task_id 
                FROM {course_tasks_table_name} 
                WHERE course_id IN (
                    SELECT course_id 
                    FROM {course_cohorts_table_name} 
                    WHERE cohort_id = ?
                )
            )
        )
        GROUP BY activity_date
    ),
    task_activity AS (
        SELECT DATE(datetime(created_at, '+5 hours', '+30 minutes')) as activity_date, COUNT(*) as count
        FROM {task_completions_table_name}
        WHERE user_id = ? 
        AND DATE(datetime(created_at, '+5 hours', '+30 minutes')) >= DATE(datetime('now', '+5 hours', '+30 minutes'), '-{n} days')
        AND task_id IN (
            SELECT task_id 
            FROM {course_tasks_table_name} 
            WHERE course_id IN (
                SELECT course_id 
                FROM {course_cohorts_table_name} 
                WHERE cohort_id = ?
            )
        )
        GROUP BY activity_date
    )
    SELECT activity_date, count FROM chat_activity
    UNION
    SELECT activity_date, count FROM task_activity
    ORDER BY activity_date
    """,
        (user_id, cohort_id, user_id, cohort_id),
        fetch_all=True,
    )

    active_days = set()

    for date, count in activity_per_day:
        if count > 0:
            active_days.add(date)

    return list(active_days)


async def get_user_activity_for_year(user_id: int, year: int):
    # Get all chat messages for the user in the given year, grouped by day
    activity_per_day = await execute_db_operation(
        f"""
        SELECT 
            strftime('%j', datetime(timestamp, '+5 hours', '+30 minutes')) as day_of_year,
            COUNT(*) as message_count
        FROM {chat_history_table_name}
        WHERE user_id = ? 
        AND strftime('%Y', datetime(timestamp, '+5 hours', '+30 minutes')) = ?
        AND role = 'user'
        GROUP BY day_of_year
        ORDER BY day_of_year
        """,
        (user_id, str(year)),
        fetch_all=True,
    )

    # Convert to dictionary mapping day of year to message count
    activity_map = {int(day) - 1: count for day, count in activity_per_day}

    num_days = 366 if not year % 4 else 365

    data = [activity_map.get(index, 0) for index in range(num_days)]

    return data


def get_user_streak_from_usage_dates(user_usage_dates: List[str]) -> int:
    if not user_usage_dates:
        return []

    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    current_streak = []

    user_usage_dates = sorted(
        list(
            set([get_date_from_str(date_str, "IST") for date_str in user_usage_dates])
        ),
        reverse=True,
    )

    for i, date in enumerate(user_usage_dates):
        if i == 0 and (today - date).days > 1:
            # the user has not used the app yesterday or today, so the streak is broken
            break
        if i == 0 or (user_usage_dates[i - 1] - date).days == 1:
            current_streak.append(date)
        else:
            break

    if not current_streak:
        return current_streak

    for index, date in enumerate(current_streak):
        current_streak[index] = datetime.strftime(date, "%Y-%m-%d")

    return current_streak


async def get_user_streak(user_id: int, cohort_id: int):
    user_usage_dates = await execute_db_operation(
        f"""
    SELECT MAX(datetime(created_at, '+5 hours', '+30 minutes')) as created_at
    FROM {chat_history_table_name}
    WHERE user_id = ? AND question_id IN (SELECT id FROM {questions_table_name} WHERE task_id IN (SELECT task_id FROM {course_tasks_table_name} WHERE course_id IN (SELECT course_id FROM {course_cohorts_table_name} WHERE cohort_id = ?)))
    GROUP BY DATE(datetime(created_at, '+5 hours', '+30 minutes'))
    
    UNION
    
    SELECT MAX(datetime(created_at, '+5 hours', '+30 minutes')) as created_at
    FROM {task_completions_table_name}
    WHERE user_id = ? AND task_id IN (
        SELECT task_id FROM {course_tasks_table_name} 
        WHERE course_id IN (SELECT course_id FROM {course_cohorts_table_name} WHERE cohort_id = ?)
    )
    GROUP BY DATE(datetime(created_at, '+5 hours', '+30 minutes'))
    
    ORDER BY created_at DESC
    """,
        (user_id, cohort_id, user_id, cohort_id),
        fetch_all=True,
    )

    return get_user_streak_from_usage_dates(
        [date_str for date_str, in user_usage_dates]
    )


async def get_cohort_streaks(
    view: LeaderboardViewType = LeaderboardViewType.ALL_TIME, cohort_id: int = None
):
    # Build date filter based on duration
    date_filter = ""
    if view == LeaderboardViewType.WEEKLY:
        date_filter = "AND DATE(datetime(timestamp, '+5 hours', '+30 minutes')) > DATE('now', 'weekday 0', '-7 days')"
    elif view == LeaderboardViewType.MONTHLY:
        date_filter = "AND strftime('%Y-%m', datetime(timestamp, '+5 hours', '+30 minutes')) = strftime('%Y-%m', 'now')"

    # Get all user interactions, ordered by user and timestamp
    usage_per_user = await execute_db_operation(
        f"""
    SELECT 
        u.id,
        u.email,
        u.first_name,
        u.middle_name,
        u.last_name,
        GROUP_CONCAT(t.created_at) as created_ats
    FROM {users_table_name} u
    LEFT JOIN (
        -- Chat history interactions
        SELECT user_id, MAX(datetime(created_at, '+5 hours', '+30 minutes')) as created_at
        FROM {chat_history_table_name}
        WHERE 1=1 {date_filter} AND question_id IN (SELECT id FROM {questions_table_name} WHERE task_id IN (SELECT task_id FROM {course_tasks_table_name} WHERE course_id IN (SELECT course_id FROM {course_cohorts_table_name} WHERE cohort_id = ?)))
        GROUP BY user_id, DATE(datetime(created_at, '+5 hours', '+30 minutes'))
        
        UNION
        
        -- Task completions
        SELECT user_id, MAX(datetime(created_at, '+5 hours', '+30 minutes')) as created_at
        FROM {task_completions_table_name}
        WHERE 1=1 {date_filter} AND task_id IN (
            SELECT task_id FROM {course_tasks_table_name} 
            WHERE course_id IN (SELECT course_id FROM {course_cohorts_table_name} WHERE cohort_id = ?)
        )
        GROUP BY user_id, DATE(datetime(created_at, '+5 hours', '+30 minutes'))
        
        ORDER BY created_at DESC, user_id
    ) t ON u.id = t.user_id
    WHERE u.id IN (
        -- Users who are in the cohort as learners
        SELECT user_id FROM {user_cohorts_table_name} WHERE cohort_id = ? and role = 'learner'
       
    )
    GROUP BY u.id, u.email, u.first_name, u.middle_name, u.last_name
    """,
        (cohort_id, cohort_id, cohort_id),
        fetch_all=True,
    )

    streaks = []

    for (
        user_id,
        user_email,
        user_first_name,
        user_middle_name,
        user_last_name,
        user_usage_dates_str,
    ) in usage_per_user:

        if user_usage_dates_str:
            user_usage_dates = user_usage_dates_str.split(",")
            user_usage_dates = sorted(user_usage_dates, reverse=True)
            streak_count = len(get_user_streak_from_usage_dates(user_usage_dates))
        else:
            streak_count = 0

        streaks.append(
            {
                "user": {
                    "id": user_id,
                    "email": user_email,
                    "first_name": user_first_name,
                    "middle_name": user_middle_name,
                    "last_name": user_last_name,
                },
                "streak_count": streak_count,
            }
        )

    return streaks


async def update_tests_for_task(task_id: int, tests: List[dict]):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Delete existing tests for the task
        await cursor.execute(
            f"DELETE FROM {tests_table_name} WHERE task_id = ?",
            (task_id,),
        )

        # Insert new tests
        for test in tests:
            await cursor.execute(
                f"""
                INSERT INTO {tests_table_name} (task_id, input, output, description)
                VALUES (?, ?, ?, ?)
                """,
                (
                    task_id,
                    json.dumps(test["input"]),
                    test["output"],
                    test.get("description", None),
                ),
            )

        await conn.commit()


def delete_all_tests():
    execute_db_operation(f"DELETE FROM {tests_table_name}")


def drop_tests_table():
    execute_db_operation(f"DROP TABLE IF EXISTS {tests_table_name}")


def drop_users_table():
    execute_db_operation(f"DELETE FROM {users_table_name}")
    execute_db_operation(f"DROP TABLE IF EXISTS {users_table_name}")


def delete_all_cohort_info():
    execute_db_operation(f"DELETE FROM {user_groups_table_name}")
    execute_db_operation(f"DELETE FROM {groups_table_name}")
    execute_db_operation(f"DELETE FROM {cohorts_table_name}")


async def delete_cohort(cohort_id: int):
    await execute_multiple_db_operations(
        [
            (
                f"DELETE FROM {user_groups_table_name} WHERE group_id IN (SELECT id FROM {groups_table_name} WHERE cohort_id = ?)",
                (cohort_id,),
            ),
            (
                f"DELETE FROM {groups_table_name} WHERE cohort_id = ?",
                (cohort_id,),
            ),
            (
                f"DELETE FROM {user_cohorts_table_name} WHERE cohort_id = ?",
                (cohort_id,),
            ),
            (
                f"DELETE FROM {course_cohorts_table_name} WHERE cohort_id = ?",
                (cohort_id,),
            ),
            (
                f"DELETE FROM {cohorts_table_name} WHERE id = ?",
                (cohort_id,),
            ),
        ]
    )


def drop_cohorts_table():
    execute_db_operation(f"DROP TABLE IF EXISTS {cohorts_table_name}")
    execute_db_operation(f"DROP TABLE IF EXISTS {groups_table_name}")
    execute_db_operation(f"DROP TABLE IF EXISTS {user_groups_table_name}")


async def create_cohort(name: str, org_id: int) -> int:
    return await execute_db_operation(
        f"""
        INSERT INTO {cohorts_table_name} (name, org_id)
        VALUES (?, ?)
        """,
        params=(name, org_id),
        get_last_row_id=True,
    )


def convert_user_db_to_dict(user: Tuple) -> Dict:
    if not user:
        return

    return {
        "id": user[0],
        "email": user[1],
        "first_name": user[2],
        "middle_name": user[3],
        "last_name": user[4],
        "default_dp_color": user[5],
        "created_at": user[6],
    }


async def insert_or_return_user(
    cursor,
    email: str,
    given_name: str = None,
    family_name: str = None,
):
    """
    Inserts a new user or returns an existing user.

    Args:
        email: The user's email address.
        given_name: The user's given name (first and middle names).
        family_name: The user's family name (last name).
        cursor: An existing database cursor

    Returns:
        A dictionary representing the user.

    Raises:
        Any exception raised by the database operations.
    """

    if given_name is None:
        first_name = None
        middle_name = None
    else:
        given_name_parts = given_name.split(" ")
        first_name = given_name_parts[0]
        middle_name = " ".join(given_name_parts[1:])
        if not middle_name:
            middle_name = None

    # if user exists, no need to do anything, just return the user
    await cursor.execute(
        f"""SELECT * FROM {users_table_name} WHERE email = ?""",
        (email,),
    )

    user = await cursor.fetchone()

    if user:
        user = convert_user_db_to_dict(user)
        if user["first_name"] is None and first_name:
            user = await update_user(
                cursor,
                user["id"],
                first_name,
                middle_name,
                family_name,
                user["default_dp_color"],
            )

        return user

    # create a new user
    color = generate_random_color()
    await cursor.execute(
        f"""
        INSERT INTO {users_table_name} (email, default_dp_color, first_name, middle_name, last_name)
        VALUES (?, ?, ?, ?, ?)
    """,
        (email, color, first_name, middle_name, family_name),
    )

    await cursor.execute(
        f"""SELECT * FROM {users_table_name} WHERE email = ?""",
        (email,),
    )

    user = convert_user_db_to_dict(await cursor.fetchone())

    return user


async def add_members_to_cohort(
    cohort_id: int, org_slug: str, org_id: int, emails: List[str], roles: List[str]
):
    if org_slug is None and org_id is None:
        raise Exception("Either org_slug or org_id must be provided")

    if org_slug is not None:
        org_id = await execute_db_operation(
            f"SELECT id FROM {organizations_table_name} WHERE slug = ?",
            (org_slug,),
            fetch_one=True,
        )

        if org_id is None:
            raise Exception("Organization not found")

        org_id = org_id[0]
    else:
        org = await execute_db_operation(
            f"SELECT id FROM {organizations_table_name} WHERE id = ?",
            (org_id,),
            fetch_one=True,
        )

        if org is None:
            raise Exception("Organization not found")

    # Check if cohort belongs to the organization
    cohort_exists = await execute_db_operation(
        f"""
        SELECT 1 FROM {cohorts_table_name} WHERE id = ? AND org_id = ?
        """,
        (cohort_id, org_id),
        fetch_one=True,
    )

    if not cohort_exists:
        raise Exception("Cohort does not belong to this organization")

    # Check if any of the emails is an admin for the org
    admin_emails = await execute_db_operation(
        f"""
        SELECT email FROM {users_table_name} u
        JOIN {user_organizations_table_name} uo ON u.id = uo.user_id
        WHERE uo.org_id = ?
        AND (uo.role = 'admin' OR uo.role = 'owner')
        AND u.email IN ({','.join(['?' for _ in emails])})
        """,
        (org_id, *emails),
        fetch_all=True,
    )

    if admin_emails:
        raise Exception(f"Cannot add an admin to the cohort.")

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        users_to_add = []
        for email in emails:
            # Get or create user
            user = await insert_or_return_user(
                cursor,
                email,
            )
            users_to_add.append(user["id"])

        await cursor.execute(
            f"""
            SELECT 1 FROM {user_cohorts_table_name} WHERE user_id IN ({','.join(['?' for _ in users_to_add])}) AND cohort_id = ?
            """,
            (*users_to_add, cohort_id),
        )

        user_exists = await cursor.fetchone()

        if user_exists:
            raise Exception("User already exists in cohort")

        # Add users to cohort
        await cursor.executemany(
            f"""
            INSERT INTO {user_cohorts_table_name} (user_id, cohort_id, role)
            VALUES (?, ?, ?)
            """,
            [(user_id, cohort_id, role) for user_id, role in zip(users_to_add, roles)],
        )
        await conn.commit()


async def update_cohort_group_name(group_id: int, new_name: str):
    await execute_db_operation(
        f"UPDATE {groups_table_name} SET name = ? WHERE id = ?",
        params=(new_name, group_id),
    )


async def add_members_to_cohort_group(cursor, group_id: int, member_ids: List[int]):
    # Check if any members already exist in the group
    member_exists = await execute_db_operation(
        f"""
        SELECT 1 FROM {user_groups_table_name} 
        WHERE group_id = ? AND user_id IN ({','.join(['?' for _ in member_ids])})
        """,
        (group_id, *member_ids),
        fetch_one=True,
    )

    if member_exists:
        raise Exception("Member already exists in group")

    await cursor.executemany(
        f"INSERT INTO {user_groups_table_name} (user_id, group_id) VALUES (?, ?)",
        [(member_id, group_id) for member_id in member_ids],
    )


async def remove_members_from_cohort_group(group_id: int, member_ids: List[int]):
    all_members_exist = await execute_db_operation(
        f"""
        SELECT 1 FROM {user_groups_table_name} 
        WHERE group_id = ? AND user_id IN ({','.join(['?' for _ in member_ids])})
        """,
        (group_id, *member_ids),
        fetch_all=True,
    )

    if len(all_members_exist) != len(member_ids):
        raise Exception("One or more members are not in the group")

    await execute_db_operation(
        f"DELETE FROM {user_groups_table_name} WHERE group_id = ? AND user_id IN ({','.join(['?' for _ in member_ids])})",
        (group_id, *member_ids),
    )


async def create_cohort_group(cohort_id: int, name: str, member_ids: List[int]):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Create the group
        await cursor.execute(
            f"""
            INSERT INTO {groups_table_name} (name, cohort_id)
            VALUES (?, ?)
            """,
            (name, cohort_id),
        )
        group_id = cursor.lastrowid

        await add_members_to_cohort_group(
            cursor,
            group_id,
            member_ids,
        )

        await conn.commit()

        return group_id


async def delete_cohort_group(group_id: int):
    await execute_multiple_db_operations(
        [
            (f"DELETE FROM {user_groups_table_name} WHERE group_id = ?", (group_id,)),
            (f"DELETE FROM {groups_table_name} WHERE id = ?", (group_id,)),
        ]
    )


async def remove_members_from_cohort(cohort_id: int, member_ids: List[int]):
    members_in_cohort = await execute_db_operation(
        f"""
        SELECT user_id FROM {user_cohorts_table_name}
        WHERE cohort_id = ? AND user_id IN ({','.join(['?' for _ in member_ids])})
        """,
        (cohort_id, *member_ids),
        fetch_all=True,
    )

    if len(members_in_cohort) != len(member_ids):
        raise Exception("One or more members are not in the cohort")

    await execute_multiple_db_operations(
        [
            (
                f"""
            DELETE FROM {user_groups_table_name} 
            WHERE user_id IN ({','.join(['?' for _ in member_ids])})
            AND group_id IN (
                SELECT id FROM {groups_table_name} 
                WHERE cohort_id = ?
            )
            """,
                (*member_ids, cohort_id),
            ),
            (
                f"""
            DELETE FROM {user_cohorts_table_name}
            WHERE user_id IN ({','.join(['?' for _ in member_ids])})
            AND cohort_id = ?
            """,
                (*member_ids, cohort_id),
            ),
        ]
    )


async def get_cohorts_for_org(org_id: int) -> List[Dict]:
    """Get all cohorts that belong to an organization"""
    results = await execute_db_operation(
        f"""
        SELECT c.id, c.name, o.id, o.name
        FROM {cohorts_table_name} c
        JOIN {organizations_table_name} o ON o.id = c.org_id
        WHERE o.id = ?
        """,
        (org_id,),
        fetch_all=True,
    )

    # Convert results into nested dict structure
    return [
        {"id": cohort_id, "name": cohort_name, "org_id": org_id, "org_name": org_name}
        for cohort_id, cohort_name, org_id, org_name in results
    ]


async def get_all_cohorts_for_org(org_id: int):
    cohorts = await execute_db_operation(
        f"""
        SELECT c.id, c.name
        FROM {cohorts_table_name} c
        WHERE c.org_id = ?
        ORDER BY c.id DESC
        """,
        (org_id,),
        fetch_all=True,
    )

    return [{"id": row[0], "name": row[1]} for row in cohorts]


async def get_cohort_by_id(cohort_id: int):
    # Fetch cohort details
    cohort = await execute_db_operation(
        f"""SELECT * FROM {cohorts_table_name} WHERE id = ?""",
        (cohort_id,),
        fetch_one=True,
    )

    if not cohort:
        return None

    # Get groups and their members
    groups = await execute_db_operation(
        f"""
        SELECT 
            g.id,
            g.name,
            GROUP_CONCAT(COALESCE(u.id, '')) as user_ids,
            GROUP_CONCAT(COALESCE(u.email, '')) as user_emails,
            GROUP_CONCAT(COALESCE(uc.role, '')) as user_roles
        FROM {groups_table_name} g
        LEFT JOIN {user_groups_table_name} ug ON g.id = ug.group_id 
        LEFT JOIN {users_table_name} u ON ug.user_id = u.id
        LEFT JOIN {user_cohorts_table_name} uc ON uc.user_id = u.id AND uc.cohort_id = g.cohort_id
        WHERE g.cohort_id = ?
        GROUP BY g.id, g.name
        ORDER BY g.id
        """,
        (cohort_id,),
        fetch_all=True,
    )

    # Get all users and their roles in the cohort
    members = await execute_db_operation(
        f"""
        SELECT DISTINCT u.id, u.email, uc.role
        FROM {users_table_name} u
        JOIN {user_cohorts_table_name} uc ON u.id = uc.user_id 
        WHERE uc.cohort_id = ?
        ORDER BY uc.role
        """,
        (cohort_id,),
        fetch_all=True,
    )

    cohort_data = {
        "id": cohort[0],
        "org_id": cohort[2],
        "name": cohort[1],
        "members": [
            {"id": member[0], "email": member[1], "role": member[2]}
            for member in members
        ],
        "groups": [
            {
                "id": group[0],
                "name": group[1],
                "members": [
                    {"id": int(user_id), "email": user_email, "role": user_role}
                    for user_id, user_email, user_role in zip(
                        group[2].split(","),
                        group[3].split(","),
                        group[4].split(","),
                    )
                    if user_id != ""
                ],
            }
            for group in groups
        ],
    }

    return cohort_data


async def is_user_in_cohort(user_id: int, cohort_id: int):
    output = await execute_db_operation(
        f"""
        SELECT COUNT(*) > 0 FROM (
            SELECT 1
            FROM {user_cohorts_table_name} uc
            WHERE uc.user_id = ? AND uc.cohort_id = ?
            UNION
            SELECT 1 
            FROM {cohorts_table_name} c
            JOIN {organizations_table_name} o ON o.id = c.org_id
            JOIN {user_organizations_table_name} ou ON ou.org_id = o.id
            WHERE c.id = ? AND ou.user_id = ? AND ou.role IN ('admin', 'owner')
        )
        """,
        (user_id, cohort_id, cohort_id, user_id),
        fetch_one=True,
    )

    return output[0]


def format_user_cohort_group(group: Tuple):
    learners = []
    for id, email in zip(group[2].split(","), group[3].split(",")):
        learners.append({"id": int(id), "email": email})

    return {
        "id": group[0],
        "name": group[1],
        "learners": learners,
    }


async def get_mentor_cohort_groups(user_id: int, cohort_id: int):
    groups = await execute_db_operation(
        f"""
        WITH mentor_groups AS (
            SELECT g.id as group_id, g.name as group_name, g.cohort_id as cohort_id
            FROM {user_groups_table_name} ug
            JOIN {groups_table_name} g ON ug.group_id = g.id
            JOIN {user_cohorts_table_name} uc ON uc.user_id = ug.user_id AND uc.cohort_id = g.cohort_id
            WHERE ug.user_id = ? AND uc.role = '{group_role_mentor}' AND g.cohort_id = ?
        ),
        learners AS (
            SELECT mg.group_id, mg.group_name, GROUP_CONCAT(u.email) as learner_emails, GROUP_CONCAT(u.id) as learner_ids
            FROM mentor_groups mg
            JOIN {user_groups_table_name} ug ON ug.group_id = mg.group_id 
            JOIN {users_table_name} u ON u.id = ug.user_id
            JOIN {user_cohorts_table_name} uc ON uc.user_id = ug.user_id AND uc.cohort_id = mg.cohort_id
            WHERE uc.role = '{group_role_learner}'
            GROUP BY mg.group_id, mg.group_name
        )
        SELECT group_id, group_name, learner_ids, learner_emails
        FROM learners
        """,
        params=(user_id, cohort_id),
        fetch_all=True,
    )

    return [format_user_cohort_group(group) for group in groups]


async def get_cohort_group_ids_for_users(cohort_id: int, user_ids: List[int]):
    groups = await execute_db_operation(
        f"""
        SELECT g.id
        FROM {groups_table_name} g
        JOIN {user_groups_table_name} ug ON ug.group_id = g.id
        JOIN {users_table_name} u ON u.id = ug.user_id
        WHERE g.cohort_id = ? AND ug.user_id IN ({','.join(['?' for _ in user_ids])})
        GROUP BY g.id, g.name
        """,
        params=(cohort_id, *user_ids),
        fetch_all=True,
    )
    return [group[0] for group in groups]


def convert_milestone_db_to_dict(milestone: Tuple) -> Dict:
    return {"id": milestone[0], "name": milestone[1], "color": milestone[2]}


async def get_all_milestones():
    milestones = await execute_db_operation(
        f"SELECT id, name, color FROM {milestones_table_name}", fetch_all=True
    )

    return [convert_milestone_db_to_dict(milestone) for milestone in milestones]


async def get_all_milestones_for_org(org_id: int):
    milestones = await execute_db_operation(
        f"SELECT id, name, color FROM {milestones_table_name} WHERE org_id = ?",
        (org_id,),
        fetch_all=True,
    )

    return [convert_milestone_db_to_dict(milestone) for milestone in milestones]


async def update_milestone(milestone_id: int, name: str):
    await execute_db_operation(
        f"UPDATE {milestones_table_name} SET name = ? WHERE id = ?",
        (name, milestone_id),
    )


async def delete_milestone(milestone_id: int):
    await execute_multiple_db_operations(
        [
            (f"DELETE FROM {milestones_table_name} WHERE id = ?", (milestone_id,)),
            (
                f"UPDATE {course_tasks_table_name} SET milestone_id = NULL WHERE milestone_id = ?",
                (milestone_id,),
            ),
            (
                f"DELETE FROM {course_milestones_table_name} WHERE milestone_id = ?",
                (milestone_id,),
            ),
        ]
    )


async def get_user_metrics_for_all_milestones(user_id: int, course_id: int):
    # Get milestones with tasks
    base_results = await execute_db_operation(
        f"""
        SELECT 
            m.id AS milestone_id,
            m.name AS milestone_name,
            m.color AS milestone_color,
            COUNT(DISTINCT t.id) AS total_tasks,
            (
                SELECT COUNT(DISTINCT ch.task_id)
                FROM {chat_history_table_name} ch
                WHERE ch.user_id = ?
                AND ch.is_solved = 1
                AND ch.task_id IN (
                    SELECT t2.id 
                    FROM {tasks_table_name} t2 
                    JOIN {course_tasks_table_name} ct2 ON t2.id = ct2.task_id
                    WHERE ct2.milestone_id = m.id 
                    AND ct2.course_id = ?
                    AND t2.deleted_at IS NULL
                )
            ) AS completed_tasks
        FROM 
            {milestones_table_name} m
        LEFT JOIN 
            {course_tasks_table_name} ct ON m.id = ct.milestone_id
        LEFT JOIN
            {tasks_table_name} t ON ct.task_id = t.id
        LEFT JOIN
            {course_milestones_table_name} cm ON m.id = cm.milestone_id AND ct.course_id = cm.course_id
        WHERE 
            t.verified = 1 AND ct.course_id = ? AND t.deleted_at IS NULL
        GROUP BY 
            m.id, m.name, m.color
        HAVING 
            COUNT(DISTINCT t.id) > 0
        ORDER BY 
            cm.ordering
        """,
        params=(user_id, course_id, course_id),
        fetch_all=True,
    )

    # Get tasks with null milestone_id
    null_milestone_results = await execute_db_operation(
        f"""
        SELECT 
            NULL AS milestone_id,
            '{uncategorized_milestone_name}' AS milestone_name,
            '{uncategorized_milestone_color}' AS milestone_color,
            COUNT(DISTINCT t.id) AS total_tasks,
            (
                SELECT COUNT(DISTINCT ch.task_id)
                FROM {chat_history_table_name} ch
                WHERE ch.user_id = ?
                AND ch.is_solved = 1
                AND ch.task_id IN (
                    SELECT t2.id 
                    FROM {tasks_table_name} t2 
                    JOIN {course_tasks_table_name} ct2 ON t2.id = ct2.task_id
                    WHERE ct2.milestone_id IS NULL 
                    AND ct2.course_id = ?
                    AND t2.deleted_at IS NULL
                )
            ) AS completed_tasks
        FROM 
            {tasks_table_name} t
        LEFT JOIN
            {course_tasks_table_name} ct ON t.id = ct.task_id
        WHERE 
            ct.milestone_id IS NULL 
            AND t.verified = 1 
            AND t.deleted_at IS NULL
            AND ct.course_id = ?
        HAVING
            COUNT(DISTINCT t.id) > 0
        ORDER BY 
            ct.ordering
        """,
        params=(user_id, course_id, course_id),
        fetch_all=True,
    )

    results = base_results + null_milestone_results

    return [
        {
            "milestone_id": row[0],
            "milestone_name": row[1],
            "milestone_color": row[2],
            "total_tasks": row[3],
            "completed_tasks": row[4],
        }
        for row in results
    ]


async def get_cohort_analytics_metrics_for_tasks(cohort_id: int, task_ids: List[int]):
    results = await execute_db_operation(
        f"""
        WITH cohort_learners AS (
            SELECT u.id, u.email
            FROM {users_table_name} u
            JOIN {user_cohorts_table_name} uc ON u.id = uc.user_id
            WHERE uc.cohort_id = ? AND uc.role = 'learner'
        ),
        task_completion AS (
            SELECT
                cl.id as user_id,
                cl.email,
                ch.task_id,
                MAX(COALESCE(ch.is_solved, 0)) as is_solved
            FROM cohort_learners cl
            INNER JOIN {chat_history_table_name} ch
                ON cl.id = ch.user_id
                AND ch.task_id IN ({','.join('?' * len(task_ids))})
            INNER JOIN {tasks_table_name} t
                ON ch.task_id = t.id
            GROUP BY cl.id, cl.email, ch.task_id, t.name
        )
        SELECT
            user_id,
            email,
            GROUP_CONCAT(task_id) as task_ids,
            GROUP_CONCAT(is_solved) as task_completion
        FROM task_completion
        GROUP BY user_id, email
        """,
        (cohort_id, *task_ids),
        fetch_all=True,
    )

    user_metrics = []
    task_metrics = defaultdict(list)
    for row in results:
        user_task_completions = [
            int(x) if x else 0 for x in (row[3].split(",") if row[3] else [])
        ]
        user_task_ids = list(map(int, row[2].split(","))) if row[2] else []

        for task_id, task_completion in zip(user_task_ids, user_task_completions):
            task_metrics[task_id].append(task_completion)

        for task_id in task_ids:
            if task_id in user_task_ids:
                continue

            # this user did not attempt this task - add default
            task_metrics[task_id].append(0)

        num_completed = sum(user_task_completions)

        user_metrics.append(
            {
                "user_id": row[0],
                "email": row[1],
                "num_completed": num_completed,
            }
        )

    task_metrics = {task_id: task_metrics[task_id] for task_id in task_ids}

    for index, row in enumerate(user_metrics):
        for task_id in task_ids:
            row[f"task_{task_id}"] = task_metrics[task_id][index]

    return user_metrics


async def get_cohort_attempt_data_for_tasks(cohort_id: int, task_ids: List[int]):
    results = await execute_db_operation(
        f"""
        WITH cohort_learners AS (
            SELECT u.id, u.email
            FROM {users_table_name} u
            JOIN {user_cohorts_table_name} uc ON u.id = uc.user_id 
            WHERE uc.cohort_id = ? AND uc.role = 'learner'
        ),
        task_attempts AS (
            SELECT 
                cl.id as user_id,
                cl.email,
                ch.task_id,
                CASE WHEN COUNT(ch.id) > 0 THEN 1 ELSE 0 END as has_attempted
            FROM cohort_learners cl
            INNER JOIN {chat_history_table_name} ch 
                ON cl.id = ch.user_id 
                AND ch.task_id IN ({','.join('?' * len(task_ids))})
            INNER JOIN {tasks_table_name} t
                ON ch.task_id = t.id
            GROUP BY cl.id, cl.email, ch.task_id, t.name
        )
        SELECT 
            user_id,
            email,
            GROUP_CONCAT(task_id) as task_ids,
            GROUP_CONCAT(has_attempted) as task_attempts
        FROM task_attempts
        GROUP BY user_id, email
        """,
        (cohort_id, *task_ids),
        fetch_all=True,
    )

    user_metrics = []
    task_attempts = defaultdict(list)

    for row in results:
        user_task_attempts_data = [
            int(x) if x else 0 for x in (row[3].split(",") if row[3] else [])
        ]
        user_task_ids = list(map(int, row[2].split(","))) if row[2] else []

        for task_id, task_attempt in zip(user_task_ids, user_task_attempts_data):
            task_attempts[task_id].append(task_attempt)

        for task_id in task_ids:
            if task_id in user_task_ids:
                continue

            task_attempts[task_id].append(0)

        num_attempted = sum(user_task_attempts_data)

        user_metrics.append(
            {
                "user_id": row[0],
                "email": row[1],
                "num_attempted": num_attempted,
            }
        )

    task_attempts = {task_id: task_attempts[task_id] for task_id in task_ids}

    for index, row in enumerate(user_metrics):
        for task_id in task_ids:
            row[f"task_{task_id}"] = task_attempts[task_id][index]

    return user_metrics


async def update_user(
    cursor,
    user_id: str,
    first_name: str,
    middle_name: str,
    last_name: str,
    default_dp_color: str,
):
    await cursor.execute(
        f"UPDATE {users_table_name} SET first_name = ?, middle_name = ?, last_name = ?, default_dp_color = ? WHERE id = ?",
        (first_name, middle_name, last_name, default_dp_color, user_id),
    )

    user = await get_user_by_id(user_id)
    return user


async def get_all_users():
    users = await execute_db_operation(
        f"SELECT * FROM {users_table_name}",
        fetch_all=True,
    )

    return [convert_user_db_to_dict(user) for user in users]


async def get_user_by_email(email: str) -> Dict:
    user = await execute_db_operation(
        f"SELECT * FROM {users_table_name} WHERE email = ?", (email,), fetch_one=True
    )

    return convert_user_db_to_dict(user)


async def get_user_by_id(user_id: str) -> Dict:
    user = await execute_db_operation(
        f"SELECT * FROM {users_table_name} WHERE id = ?", (user_id,), fetch_one=True
    )

    return convert_user_db_to_dict(user)


async def get_user_cohorts(user_id: int) -> List[Dict]:
    """Get all cohorts (and the groups in each cohort) that the user is a part of along with their role in each group"""
    results = await execute_db_operation(
        f"""
        SELECT c.id, c.name, uc.role, o.id, o.name
        FROM {cohorts_table_name} c
        JOIN {user_cohorts_table_name} uc ON uc.cohort_id = c.id
        JOIN {organizations_table_name} o ON o.id = c.org_id
        WHERE uc.user_id = ?
        """,
        (user_id,),
        fetch_all=True,
    )

    # Convert results into nested dict structure
    return [
        {
            "id": cohort_id,
            "name": cohort_name,
            "org_id": org_id,
            "org_name": org_name,
            "role": role,
        }
        for cohort_id, cohort_name, role, org_id, org_name in results
    ]


async def create_badge_for_user(
    user_id: int,
    value: str,
    badge_type: str,
    image_path: str,
    bg_color: str,
    cohort_id: int,
) -> int:
    return await execute_db_operation(
        f"INSERT INTO {badges_table_name} (user_id, value, type, image_path, bg_color, cohort_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, value, badge_type, image_path, bg_color, cohort_id),
        get_last_row_id=True,
    )


async def update_badge(
    badge_id: int, value: str, badge_type: str, image_path: str, bg_color: str
):
    await execute_db_operation(
        f"UPDATE {badges_table_name} SET value = ?, type = ?, image_path = ?, bg_color = ? WHERE id = ?",
        (value, badge_type, image_path, bg_color, badge_id),
    )


def convert_badge_db_to_dict(badge: Tuple):
    if badge is None:
        return

    output = {
        "id": badge[0],
        "user_id": badge[1],
        "value": badge[2],
        "type": badge[3],
        "image_path": badge[4],
        "bg_color": badge[5],
    }

    if len(badge) > 6:
        output["cohort_name"] = badge[6]
        output["org_name"] = badge[7]

    return output


async def get_badge_by_id(badge_id: int) -> Dict:
    badge = await execute_db_operation(
        f"SELECT b.id, b.user_id, b.value, b.type, b.image_path, b.bg_color, c.name, o.name FROM {badges_table_name} b LEFT JOIN {cohorts_table_name} c ON c.id = b.cohort_id LEFT JOIN {organizations_table_name} o ON o.id = c.org_id WHERE b.id = ?",
        (badge_id,),
        fetch_one=True,
    )

    return convert_badge_db_to_dict(badge)


async def get_badges_by_user_id(user_id: int) -> List[Dict]:
    badges = await execute_db_operation(
        f"SELECT b.id, b.user_id, b.value, b.type, b.image_path, b.bg_color, c.name, o.name FROM {badges_table_name} b LEFT JOIN {cohorts_table_name} c ON c.id = b.cohort_id LEFT JOIN {organizations_table_name} o ON o.id = c.org_id WHERE b.user_id = ? ORDER BY b.id DESC",
        (user_id,),
        fetch_all=True,
    )

    return [convert_badge_db_to_dict(badge) for badge in badges]


async def get_cohort_badge_by_type_and_user_id(
    user_id: int, badge_type: str, cohort_id: int
) -> Dict:
    badge = await execute_db_operation(
        f"SELECT id, user_id, value, type, image_path, bg_color FROM {badges_table_name} WHERE user_id = ? AND type = ? AND cohort_id = ?",
        (user_id, badge_type, cohort_id),
        fetch_one=True,
    )

    return convert_badge_db_to_dict(badge)


async def delete_badge_by_id(badge_id: int):
    await execute_db_operation(
        f"DELETE FROM {badges_table_name} WHERE id = ?",
        (badge_id,),
    )


def clear_badges_table():
    execute_db_operation(f"DELETE FROM {badges_table_name}")


def drop_badges_table():
    execute_multiple_db_operations(
        [
            (f"DELETE FROM {badges_table_name}", ()),
            (f"DROP TABLE IF EXISTS {badges_table_name}", ()),
        ]
    )


async def add_cv_review_usage(user_id: int, role: str, ai_review: str):
    await execute_db_operation(
        f"INSERT INTO {cv_review_usage_table_name} (user_id, role, ai_review) VALUES (?, ?, ?)",
        (user_id, role, ai_review),
    )


def transform_cv_review_usage_to_dict(cv_review_usage: Tuple):
    return {
        "id": cv_review_usage[0],
        "user_id": cv_review_usage[1],
        "user_email": cv_review_usage[2],
        "role": cv_review_usage[3],
        "ai_review": cv_review_usage[4],
        "created_at": convert_utc_to_ist(
            datetime.fromisoformat(cv_review_usage[5])
        ).isoformat(),
    }


def drop_cv_review_usage_table():
    execute_multiple_db_operations(
        [
            (f"DELETE FROM {cv_review_usage_table_name}", ()),
            (f"DROP TABLE IF EXISTS {cv_review_usage_table_name}", ()),
        ]
    )


async def get_all_cv_review_usage():
    all_cv_review_usage = await execute_db_operation(
        f"""
        SELECT cv.id, cv.user_id, u.email, cv.role, cv.ai_review , cv.created_at
        FROM {cv_review_usage_table_name} cv
        JOIN users u ON cv.user_id = u.id
        """,
        fetch_all=True,
    )

    return [
        transform_cv_review_usage_to_dict(cv_review_usage)
        for cv_review_usage in all_cv_review_usage
    ]


def drop_user_organizations_table():
    execute_multiple_db_operations(
        [
            (f"DELETE FROM {user_organizations_table_name}", ()),
            (f"DROP TABLE IF EXISTS {user_organizations_table_name}", ()),
        ]
    )


def drop_organizations_table():
    drop_user_organizations_table()

    execute_multiple_db_operations(
        [
            (f"DELETE FROM {organizations_table_name}", ()),
            (f"DROP TABLE IF EXISTS {organizations_table_name}", ()),
        ]
    )


async def update_org(org_id: int, org_name: str):
    await execute_db_operation(
        f"UPDATE {organizations_table_name} SET name = ? WHERE id = ?",
        (org_name, org_id),
    )


async def update_org_openai_api_key(
    org_id: int, encrypted_openai_api_key: str, is_free_trial: bool
):
    await execute_db_operation(
        f"UPDATE {organizations_table_name} SET openai_api_key = ?, openai_free_trial = ? WHERE id = ?",
        (encrypted_openai_api_key, is_free_trial, org_id),
    )


async def clear_org_openai_api_key(org_id: int):
    await execute_db_operation(
        f"UPDATE {organizations_table_name} SET openai_api_key = NULL WHERE id = ?",
        (org_id,),
    )


async def add_user_to_org_by_user_id(
    cursor,
    user_id: int,
    org_id: int,
    role: Literal["owner", "admin"],
):
    await cursor.execute(
        f"""INSERT INTO {user_organizations_table_name}
            (user_id, org_id, role)
            VALUES (?, ?, ?)""",
        (user_id, org_id, role),
    )

    return cursor.lastrowid


async def create_organization_with_user(org_name: str, slug: str, user_id: int):
    # Check if organization with the given slug already exists
    existing_org = await execute_db_operation(
        f"SELECT id FROM {organizations_table_name} WHERE slug = ?",
        (slug,),
        fetch_one=True,
    )

    if existing_org:
        raise Exception(f"Organization with slug '{slug}' already exists")

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"""INSERT INTO {organizations_table_name} 
                (slug, name)
                VALUES (?, ?)""",
            (slug, org_name),
        )

        org_id = cursor.lastrowid

        await add_user_to_org_by_user_id(cursor, user_id, org_id, "owner")

        await conn.commit()

    return org_id


def convert_org_db_to_dict(org: Tuple):
    if not org:
        return None

    return {
        "id": org[0],
        "slug": org[1],
        "name": org[2],
        "logo_color": org[3],
        "openai_api_key": org[5],
        "openai_free_trial": org[6],
    }


async def get_org_by_id(org_id: int):
    org_details = await execute_db_operation(
        f"SELECT * FROM {organizations_table_name} WHERE id = ?",
        (org_id,),
        fetch_one=True,
    )

    return convert_org_db_to_dict(org_details)


async def get_org_by_slug(slug: str):
    org_details = await execute_db_operation(
        f"SELECT * FROM {organizations_table_name} WHERE slug = ?",
        (slug,),
        fetch_one=True,
    )
    return convert_org_db_to_dict(org_details)


async def get_hva_org_id():
    hva_org_id = await execute_db_operation(
        "SELECT id FROM organizations WHERE name = ?",
        ("HyperVerge Academy",),
        fetch_one=True,
    )

    if hva_org_id is None:
        return None

    hva_org_id = hva_org_id[0]
    return hva_org_id


async def get_hva_cohort_ids() -> List[int]:
    hva_org_id = await get_hva_org_id()

    if hva_org_id is None:
        return []

    cohorts = await execute_db_operation(
        "SELECT id FROM cohorts WHERE org_id = ?",
        (hva_org_id,),
        fetch_all=True,
    )
    return [cohort[0] for cohort in cohorts]


async def is_user_hva_learner(user_id: int) -> bool:
    hva_cohort_ids = await get_hva_cohort_ids()

    if not hva_cohort_ids:
        return False

    num_hva_users_matching_user_id = (
        await execute_db_operation(
            f"SELECT COUNT(*) FROM user_cohorts WHERE user_id = ? AND cohort_id IN ({', '.join(map(str, hva_cohort_ids))}) AND role = 'learner'",
            (user_id,),
            fetch_one=True,
        )
    )[0]

    return num_hva_users_matching_user_id > 0


async def get_hva_openai_api_key() -> str:
    org_details = await get_org_by_id(await get_hva_org_id())
    return org_details["openai_api_key"]


async def add_users_to_org_by_email(
    org_id: int,
    emails: List[str],
):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        user_ids = []
        for email in emails:
            user = await insert_or_return_user(cursor, email)
            user_ids.append(user["id"])

        # Check if any of the users are already in the organization
        placeholders = ", ".join(["?" for _ in user_ids])

        await cursor.execute(
            f"""SELECT user_id FROM {user_organizations_table_name} 
            WHERE org_id = ? AND user_id IN ({placeholders})
            """,
            (org_id, *user_ids),
        )

        existing_user_ids = await cursor.fetchall()

        if existing_user_ids:
            raise Exception(f"Some users already exist in organization")

        await cursor.executemany(
            f"""INSERT INTO {user_organizations_table_name}
                (user_id, org_id, role)
                VALUES (?, ?, ?)""",
            [(user_id, org_id, "admin") for user_id in user_ids],
        )
        await conn.commit()


async def remove_members_from_org(org_id: int, user_ids: List[int]):
    query = f"DELETE FROM {user_organizations_table_name} WHERE org_id = ? AND user_id IN ({', '.join(map(str, user_ids))})"
    await execute_db_operation(query, (org_id,))


def convert_user_organization_db_to_dict(user_organization: Tuple):
    return {
        "id": user_organization[0],
        "user_id": user_organization[1],
        "org_id": user_organization[2],
        "role": user_organization[3],
    }


async def get_user_organizations(user_id: int):
    user_organizations = await execute_db_operation(
        f"""SELECT uo.org_id, o.name, uo.role, o.openai_api_key, o.openai_free_trial
        FROM {user_organizations_table_name} uo
        JOIN organizations o ON uo.org_id = o.id 
        WHERE uo.user_id = ? ORDER BY uo.id DESC""",
        (user_id,),
        fetch_all=True,
    )

    return [
        {
            "id": user_organization[0],
            "name": user_organization[1],
            "role": user_organization[2],
            "openai_api_key": user_organization[3],
            "openai_free_trial": user_organization[4],
        }
        for user_organization in user_organizations
    ]


async def get_org_members(org_id: int):
    org_users = await execute_db_operation(
        f"""SELECT uo.user_id, u.email, uo.role 
        FROM {user_organizations_table_name} uo
        JOIN users u ON uo.user_id = u.id 
        WHERE uo.org_id = ?""",
        (org_id,),
        fetch_all=True,
    )

    return [
        {
            "id": org_user[0],
            "email": org_user[1],
            "role": org_user[2],
        }
        for org_user in org_users
    ]


def drop_task_tags_table():
    commands = [
        (f"DELETE FROM {task_tags_table_name}", ()),
        (f"DROP TABLE IF EXISTS {task_tags_table_name}", ()),
    ]
    execute_multiple_db_operations(commands)


def drop_tags_table():
    drop_task_tags_table()

    commands = [
        (f"DELETE FROM {tags_table_name}", ()),
        (f"DROP TABLE IF EXISTS {tags_table_name}", ()),
    ]
    execute_multiple_db_operations(commands)


async def create_tag(tag_name: str, org_id: int):
    await execute_db_operation(
        f"INSERT INTO {tags_table_name} (name, org_id) VALUES (?, ?)",
        (tag_name, org_id),
    )


async def create_bulk_tags(tag_names: List[str], org_id: int) -> bool:
    if not tag_names:
        return False

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Get existing tags
        await cursor.execute(
            f"SELECT name FROM {tags_table_name} WHERE org_id = ?", (org_id,)
        )
        existing_tags = {row[0] for row in await cursor.fetchall()}

        # Filter out tags that already exist
        new_tags = [tag for tag in tag_names if tag not in existing_tags]

        has_new_tags = len(new_tags) > 0

        # Insert new tags
        if new_tags:
            await cursor.executemany(
                f"INSERT INTO {tags_table_name} (name, org_id) VALUES (?, ?)",
                [(tag, org_id) for tag in new_tags],
            )

            await conn.commit()
            return has_new_tags


def convert_tag_db_to_dict(tag: Tuple) -> Dict:
    return {
        "id": tag[0],
        "name": tag[1],
        "created_at": convert_utc_to_ist(datetime.fromisoformat(tag[2])).isoformat(),
    }


async def get_all_tags() -> List[Dict]:
    tags = await execute_db_operation(
        f"SELECT * FROM {tags_table_name}", fetch_all=True
    )

    return [convert_tag_db_to_dict(tag) for tag in tags]


async def get_all_tags_for_org(org_id: int) -> List[Dict]:
    tags = await execute_db_operation(
        f"SELECT * FROM {tags_table_name} WHERE org_id = ?", (org_id,), fetch_all=True
    )

    return [convert_tag_db_to_dict(tag) for tag in tags]


async def delete_tag(tag_id: int):
    await execute_db_operation(f"DELETE FROM {tags_table_name} WHERE id = ?", (tag_id,))


def transfer_badge_to_user(prev_user_id: int, new_user_id: int):
    execute_db_operation(
        f"UPDATE {badges_table_name} SET user_id = ? WHERE user_id = ?",
        (new_user_id, prev_user_id),
    )


def transfer_chat_history_to_user(prev_user_id: int, new_user_id: int):
    execute_db_operation(
        f"UPDATE {chat_history_table_name} SET user_id = ? WHERE user_id = ?",
        (new_user_id, prev_user_id),
    )


def drop_user_cohorts_table():
    execute_db_operation(f"DROP TABLE IF EXISTS {user_cohorts_table_name}")


async def get_courses_for_tasks(task_ids: List[int]):
    if not task_ids:
        return []

    results = await execute_db_operation(
        f"""SELECT ct.task_id, c.id, c.name, ct.milestone_id, m.name FROM {course_tasks_table_name} ct 
        JOIN {courses_table_name} c ON ct.course_id = c.id LEFT JOIN {milestones_table_name} m ON ct.milestone_id = m.id WHERE ct.task_id IN ({', '.join(map(str, task_ids))})""",
        fetch_all=True,
    )

    task_courses = [
        {
            "task_id": result[0],
            "course": {
                "id": result[1],
                "name": result[2],
                "milestone": (
                    {
                        "id": result[3],
                        "name": result[4],
                    }
                    if result[3] is not None
                    else None
                ),
            },
        }
        for result in results
    ]

    task_id_to_courses = defaultdict(list)

    for task_course in task_courses:
        task_id_to_courses[task_course["task_id"]].append(task_course["course"])

    task_courses = []
    for task_id, courses in task_id_to_courses.items():
        task_courses.append(
            {
                "task_id": task_id,
                "courses": courses,
            }
        )

    for task_id in task_ids:
        if task_id in task_id_to_courses:
            continue

        task_courses.append(
            {
                "task_id": task_id,
                "courses": [],
            }
        )

    return task_courses


async def check_and_insert_missing_course_milestones(
    course_tasks_to_add: List[Tuple[int, int, int]],
):
    # Find unique course, milestone pairs to validate they exist
    unique_course_milestone_pairs = {
        (course_id, milestone_id)
        for _, course_id, milestone_id in course_tasks_to_add
        if milestone_id is not None
    }

    if unique_course_milestone_pairs:
        # Verify all milestone IDs exist for their respective courses
        milestone_check = await execute_db_operation(
            f"""
            SELECT course_id, milestone_id FROM {course_milestones_table_name}
            WHERE (course_id, milestone_id) IN ({','.join(['(?,?)'] * len(unique_course_milestone_pairs))})
            """,
            tuple(itertools.chain(*unique_course_milestone_pairs)),
            fetch_all=True,
        )

        found_pairs = {(row[0], row[1]) for row in milestone_check}
        pairs_not_found = unique_course_milestone_pairs - found_pairs

        if pairs_not_found:
            # For each missing pair, get the max ordering for that course and increment
            for course_id, milestone_id in pairs_not_found:
                # Get current max ordering for this course
                max_ordering = (
                    await execute_db_operation(
                        f"SELECT COALESCE(MAX(ordering), -1) FROM {course_milestones_table_name} WHERE course_id = ?",
                        (course_id,),
                        fetch_one=True,
                    )
                )[0]

                # Insert with incremented ordering
                await execute_db_operation(
                    f"INSERT INTO {course_milestones_table_name} (course_id, milestone_id, ordering) VALUES (?, ?, ?)",
                    (course_id, milestone_id, max_ordering + 1),
                )


async def add_tasks_to_courses(course_tasks_to_add: List[Tuple[int, int, int]]):
    await check_and_insert_missing_course_milestones(course_tasks_to_add)

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Group tasks by course_id
        course_to_tasks = defaultdict(list)
        for task_id, course_id, milestone_id in course_tasks_to_add:
            course_to_tasks[course_id].append((task_id, milestone_id))

        # For each course, get max ordering and insert tasks with incremented order
        for course_id, task_details in course_to_tasks.items():
            await cursor.execute(
                f"SELECT COALESCE(MAX(ordering), -1) FROM {course_tasks_table_name} WHERE course_id = ?",
                (course_id,),
            )
            max_ordering = (await cursor.fetchone())[0]

            # Insert tasks with incremented ordering
            values_to_insert = []
            for i, (task_id, milestone_id) in enumerate(task_details, start=1):
                values_to_insert.append(
                    (task_id, course_id, max_ordering + i, milestone_id)
                )

            await cursor.executemany(
                f"INSERT OR IGNORE INTO {course_tasks_table_name} (task_id, course_id, ordering, milestone_id) VALUES (?, ?, ?, ?)",
                values_to_insert,
            )

        await conn.commit()


async def remove_tasks_from_courses(course_tasks_to_remove: List[Tuple[int, int]]):
    await execute_many_db_operation(
        f"DELETE FROM {course_tasks_table_name} WHERE task_id = ? AND course_id = ?",
        params_list=course_tasks_to_remove,
    )


async def update_task_orders(task_orders: List[Tuple[int, int]]):
    await execute_many_db_operation(
        f"UPDATE {course_tasks_table_name} SET ordering = ? WHERE id = ?",
        params_list=task_orders,
    )


async def add_milestone_to_course(
    course_id: int, milestone_name: str, milestone_color: str
) -> Tuple[int, int]:
    org_id = await get_org_id_for_course(course_id)

    # Wrap the entire operation in a transaction
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Get the max ordering value for this course
        await cursor.execute(
            f"INSERT INTO {milestones_table_name} (name, color, org_id) VALUES (?, ?, ?)",
            (milestone_name, milestone_color, org_id),
        )

        milestone_id = cursor.lastrowid

        await cursor.execute(
            f"SELECT COALESCE(MAX(ordering), -1) FROM {course_milestones_table_name} WHERE course_id = ?",
            (course_id,),
        )
        max_ordering = await cursor.fetchone()

        # Set the new milestone's order to be the next value
        next_order = max_ordering[0] + 1 if max_ordering else 0

        await cursor.execute(
            f"INSERT INTO {course_milestones_table_name} (course_id, milestone_id, ordering) VALUES (?, ?, ?)",
            (course_id, milestone_id, next_order),
        )

        await conn.commit()

        return milestone_id, next_order


async def update_milestone_orders(milestone_orders: List[Tuple[int, int]]):
    await execute_many_db_operation(
        f"UPDATE {course_milestones_table_name} SET ordering = ? WHERE id = ?",
        params_list=milestone_orders,
    )


async def swap_milestone_ordering_for_course(
    course_id: int, milestone_1_id: int, milestone_2_id: int
):
    # First, check if both milestones exist for the course
    milestone_entries = await execute_db_operation(
        f"SELECT milestone_id, ordering FROM {course_milestones_table_name} WHERE course_id = ? AND milestone_id IN (?, ?)",
        (course_id, milestone_1_id, milestone_2_id),
        fetch_all=True,
    )

    if len(milestone_entries) != 2:
        raise ValueError("One or both milestones do not exist for this course")

    # Get the IDs and orderings for the course_milestones entries
    milestone_1_id, milestone_1_ordering = milestone_entries[0]
    milestone_2_id, milestone_2_ordering = milestone_entries[1]

    update_params = [
        (milestone_2_ordering, milestone_1_id),
        (milestone_1_ordering, milestone_2_id),
    ]

    await execute_many_db_operation(
        f"UPDATE {course_milestones_table_name} SET ordering = ? WHERE id = ?",
        params_list=update_params,
    )


async def swap_task_ordering_for_course(course_id: int, task_1_id: int, task_2_id: int):
    # First, check if both tasks exist for the course
    task_entries = await execute_db_operation(
        f"SELECT task_id, milestone_id, ordering FROM {course_tasks_table_name} WHERE course_id = ? AND task_id IN (?, ?)",
        (course_id, task_1_id, task_2_id),
        fetch_all=True,
    )

    if len(task_entries) != 2:
        raise ValueError("One or both tasks do not exist for this course")

    # Get the IDs and orderings for the course_tasks entries
    task_1_id, task_1_milestone_id, task_1_ordering = task_entries[0]
    task_2_id, task_2_milestone_id, task_2_ordering = task_entries[1]

    if task_1_milestone_id != task_2_milestone_id:
        raise ValueError("Tasks are not in the same milestone")

    update_params = [
        (task_2_ordering, task_1_id),
        (task_1_ordering, task_2_id),
    ]

    await execute_many_db_operation(
        f"UPDATE {course_tasks_table_name} SET ordering = ? WHERE id = ?",
        params_list=update_params,
    )


async def remove_scoring_criteria_from_task(scoring_criteria_ids: List[int]):
    if not scoring_criteria_ids:
        return

    await execute_db_operation(
        f"""DELETE FROM {task_scoring_criteria_table_name} 
            WHERE id IN ({', '.join(map(str, scoring_criteria_ids))})"""
    )


async def add_scoring_criteria_to_tasks(
    task_ids: List[int], scoring_criteria: List[Dict]
):
    if not scoring_criteria:
        return

    params = list(
        itertools.chain(
            *[
                [
                    (
                        task_id,
                        criterion["category"],
                        criterion["description"],
                        criterion["range"][0],
                        criterion["range"][1],
                    )
                    for criterion in scoring_criteria
                ]
                for task_id in task_ids
            ]
        )
    )

    await execute_many_db_operation(
        f"""INSERT INTO {task_scoring_criteria_table_name} 
            (task_id, category, description, min_score, max_score) 
            VALUES (?, ?, ?, ?, ?)""",
        params_list=params,
    )


async def create_course(name: str, org_id: int) -> int:
    course_id = await execute_db_operation(
        f"""
        INSERT INTO {courses_table_name} (name, org_id)
        VALUES (?, ?)
        """,
        (name, org_id),
        get_last_row_id=True,
    )
    return course_id


def convert_course_db_to_dict(course: Tuple) -> Dict:
    result = {
        "id": course[0],
        "name": course[1],
    }

    if len(course) > 2:
        result["org"] = {
            "id": course[2],
            "name": course[3],
            "slug": course[4],
        }

    return result


async def get_course(course_id: int, only_published: bool = True) -> Dict:
    course = await execute_db_operation(
        f"SELECT c.id, c.name, cgj.status as course_generation_status FROM {courses_table_name} c LEFT JOIN {course_generation_jobs_table_name} cgj ON c.id = cgj.course_id WHERE c.id = ?",
        (course_id,),
        fetch_one=True,
    )

    if not course:
        return None

    # Fix the milestones query to match the actual schema
    milestones = await execute_db_operation(
        f"""SELECT m.id, m.name, m.color, cm.ordering 
            FROM {course_milestones_table_name} cm
            JOIN milestones m ON cm.milestone_id = m.id
            WHERE cm.course_id = ? ORDER BY cm.ordering""",
        (course_id,),
        fetch_all=True,
    )

    # Fetch all tasks for this course
    tasks = await execute_db_operation(
        f"""SELECT t.id, t.title, t.type, t.status, t.scheduled_publish_at, ct.milestone_id, ct.ordering,
            (CASE WHEN t.type IN ('{TaskType.QUIZ}', '{TaskType.EXAM}') THEN 
                (SELECT COUNT(*) FROM {questions_table_name} q 
                 WHERE q.task_id = t.id)
             ELSE NULL END) as num_questions,
            tgj.status as task_generation_status
            FROM {course_tasks_table_name} ct
            JOIN {tasks_table_name} t ON ct.task_id = t.id
            LEFT JOIN {task_generation_jobs_table_name} tgj ON t.id = tgj.task_id
            WHERE ct.course_id = ? AND t.deleted_at IS NULL
            {
                f"AND t.status = '{TaskStatus.PUBLISHED}' AND t.scheduled_publish_at IS NULL"
                if only_published
                else ""
            }
            ORDER BY ct.milestone_id, ct.ordering""",
        (course_id,),
        fetch_all=True,
    )

    # Group tasks by milestone_id
    tasks_by_milestone = defaultdict(list)
    for task in tasks:
        milestone_id = task[5]

        tasks_by_milestone[milestone_id].append(
            {
                "id": task[0],
                "title": task[1],
                "type": task[2],
                "status": task[3],
                "scheduled_publish_at": task[4],
                "ordering": task[6],
                "num_questions": task[7],
                "is_generating": task[8] is not None
                and task[8] == GenerateTaskJobStatus.STARTED,
            }
        )

    course_dict = {
        "id": course[0],
        "name": course[1],
        "course_generation_status": course[2],
    }
    course_dict["milestones"] = []

    for milestone in milestones:
        milestone_id = milestone[0]
        milestone_dict = {
            "id": milestone_id,
            "name": milestone[1],
            "color": milestone[2],
            "ordering": milestone[3],
            "tasks": tasks_by_milestone.get(milestone_id, []),
        }
        course_dict["milestones"].append(milestone_dict)

    return course_dict


async def update_course_name(course_id: int, name: str):
    await execute_db_operation(
        f"UPDATE {courses_table_name} SET name = ? WHERE id = ?",
        (name, course_id),
    )


async def update_cohort_name(cohort_id: int, name: str):
    await execute_db_operation(
        f"UPDATE {cohorts_table_name} SET name = ? WHERE id = ?",
        (name, cohort_id),
    )


async def get_all_courses_for_org(org_id: int):
    courses = await execute_db_operation(
        f"SELECT id, name FROM {courses_table_name} WHERE org_id = ? ORDER BY id DESC",
        (org_id,),
        fetch_all=True,
    )

    return [convert_course_db_to_dict(course) for course in courses]


async def delete_course(course_id: int):
    await execute_multiple_db_operations(
        [
            (
                f"DELETE FROM {course_cohorts_table_name} WHERE course_id = ?",
                (course_id,),
            ),
            (
                f"DELETE FROM {course_tasks_table_name} WHERE course_id = ?",
                (course_id,),
            ),
            (
                f"DELETE FROM {course_milestones_table_name} WHERE course_id = ?",
                (course_id,),
            ),
            (
                f"DELETE FROM {course_generation_jobs_table_name} WHERE course_id = ?",
                (course_id,),
            ),
            (
                f"DELETE FROM {task_generation_jobs_table_name} WHERE course_id = ?",
                (course_id,),
            ),
            (f"DELETE FROM {courses_table_name} WHERE id = ?", (course_id,)),
        ]
    )


def delete_all_courses_for_org(org_id: int):
    execute_multiple_db_operations(
        [
            (
                f"DELETE FROM {course_cohorts_table_name} WHERE course_id IN (SELECT id FROM {courses_table_name} WHERE org_id = ?)",
                (org_id,),
            ),
            (f"DELETE FROM {courses_table_name} WHERE org_id = ?", (org_id,)),
        ]
    )


async def add_course_to_cohorts(course_id: int, cohort_ids: List[int]):
    await execute_many_db_operation(
        f"INSERT INTO {course_cohorts_table_name} (course_id, cohort_id) VALUES (?, ?)",
        [(course_id, cohort_id) for cohort_id in cohort_ids],
    )


async def add_courses_to_cohort(cohort_id: int, course_ids: List[int]):
    await execute_many_db_operation(
        f"INSERT INTO {course_cohorts_table_name} (course_id, cohort_id) VALUES (?, ?)",
        [(course_id, cohort_id) for course_id in course_ids],
    )


async def remove_course_from_cohorts(course_id: int, cohort_ids: List[int]):
    await execute_many_db_operation(
        f"DELETE FROM {course_cohorts_table_name} WHERE course_id = ? AND cohort_id = ?",
        [(course_id, cohort_id) for cohort_id in cohort_ids],
    )


async def remove_courses_from_cohort(cohort_id: int, course_ids: List[int]):
    await execute_many_db_operation(
        f"DELETE FROM {course_cohorts_table_name} WHERE cohort_id = ? AND course_id = ?",
        [(cohort_id, course_id) for course_id in course_ids],
    )


async def get_courses_for_cohort(cohort_id: int, include_tree: bool = False):
    courses = await execute_db_operation(
        f"""
        SELECT c.id, c.name 
        FROM {courses_table_name} c
        JOIN {course_cohorts_table_name} cc ON c.id = cc.course_id
        WHERE cc.cohort_id = ?
        """,
        (cohort_id,),
        fetch_all=True,
    )
    courses = [{"id": course[0], "name": course[1]} for course in courses]

    if not include_tree:
        return courses

    for index, course in enumerate(courses):
        courses[index] = await get_course(course["id"])

    return courses


async def get_cohorts_for_course(course_id: int):
    cohorts = await execute_db_operation(
        f"""
        SELECT ch.id, ch.name 
        FROM {cohorts_table_name} ch
        JOIN {course_cohorts_table_name} cc ON ch.id = cc.cohort_id
        WHERE cc.course_id = ?
        """,
        (course_id,),
        fetch_all=True,
    )

    return [{"id": cohort[0], "name": cohort[1]} for cohort in cohorts]


def drop_course_cohorts_table():
    execute_multiple_db_operations(
        [
            (f"DELETE FROM {course_cohorts_table_name}", ()),
            (f"DROP TABLE IF EXISTS {course_cohorts_table_name}", ()),
        ]
    )


def drop_courses_table():
    drop_course_cohorts_table()

    execute_multiple_db_operations(
        [
            (f"DELETE FROM {courses_table_name}", ()),
            (f"DROP TABLE IF EXISTS {courses_table_name}", ()),
        ]
    )


async def get_tasks_for_course(course_id: int, milestone_id: int = None):
    query = f"""SELECT t.id, t.name, COALESCE(m.name, '{uncategorized_milestone_name}') as milestone_name, t.verified, t.input_type, t.response_type, t.coding_language, ct.ordering, ct.id as course_task_id, ct.milestone_id, t.type
        FROM {tasks_table_name} t
        JOIN {course_tasks_table_name} ct ON ct.task_id = t.id 
        LEFT JOIN {milestones_table_name} m ON ct.milestone_id = m.id
        WHERE t.deleted_at IS NULL
        """

    params = []

    if milestone_id is not None:
        query += f" AND ct.course_id = ? AND ct.milestone_id = ?"
        params.extend([course_id, milestone_id])
    else:
        query += " AND ct.course_id = ?"
        params.append(course_id)

    query += " ORDER BY ct.ordering"

    tasks = await execute_db_operation(query, tuple(params), fetch_all=True)

    return [
        {
            "id": task[0],
            "name": task[1],
            "milestone": task[2],
            "verified": task[3],
            "input_type": task[4],
            "response_type": task[5],
            "coding_language": deserialise_list_from_str(task[6]),
            "ordering": task[7],
            "course_task_id": task[8],
            "milestone_id": task[9],
            "type": task[10],
        }
        for task in tasks
    ]


async def get_milestones_for_course(course_id: int):
    milestones = await execute_db_operation(
        f"SELECT cm.id, cm.milestone_id, m.name, cm.ordering FROM {course_milestones_table_name} cm JOIN {milestones_table_name} m ON cm.milestone_id = m.id WHERE cm.course_id = ? ORDER BY cm.ordering",
        (course_id,),
        fetch_all=True,
    )
    return [
        {
            "course_milestone_id": milestone[0],
            "id": milestone[1],
            "name": milestone[2],
            "ordering": milestone[3],
        }
        for milestone in milestones
    ]


async def get_user_courses(user_id: int) -> List[Dict]:
    """
    Get all courses for a user based on different roles:
    1. Courses where the user is a learner or mentor through cohorts
    2. All courses from organizations where the user is an admin or owner

    Args:
        user_id: The ID of the user

    Returns:
        List of course dictionaries with their details and user's role
    """
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        # Get all courses where the user is a learner or mentor through cohorts
        user_cohorts = await get_user_cohorts(user_id)

        # Dictionary to track user's role in each course
        course_roles = {}
        course_to_cohort = {}

        # Add courses from user's cohorts with their roles
        for cohort in user_cohorts:
            cohort_id = cohort["id"]
            user_role_in_cohort = cohort.get("role")  # Get user's role in this cohort

            cohort_courses = await get_courses_for_cohort(cohort_id)
            for course in cohort_courses:
                course_id = course["id"]
                course_to_cohort[course_id] = cohort_id

                # Only update role if not already an admin/owner
                if course_id not in course_roles or course_roles[course_id] not in [
                    "admin",
                    "owner",
                ]:
                    course_roles[course_id] = user_role_in_cohort

        # Get organizations where the user is an admin or owner
        user_orgs = await get_user_organizations(user_id)
        admin_owner_org_ids = [
            org["id"] for org in user_orgs if org["role"] in ["admin", "owner"]
        ]

        # Add all courses from organizations where user is admin or owner
        for org_id in admin_owner_org_ids:
            org_courses = await get_all_courses_for_org(org_id)
            for course in org_courses:
                course_id = course["id"]
                # Admin/owner role takes precedence
                course_roles[course_id] = "admin"

        # If no courses found, return empty list
        if not course_roles:
            return []

        # Fetch detailed information for all course IDs
        courses = []
        for course_id, role in course_roles.items():
            # Fetch course from DB including org_id
            await cursor.execute(
                f"SELECT c.id, c.name, o.id, o.name, o.slug FROM {courses_table_name} c JOIN {organizations_table_name} o ON c.org_id = o.id WHERE c.id = ?",
                (course_id,),
            )
            course_row = await cursor.fetchone()
            if course_row:
                course_dict = convert_course_db_to_dict(course_row)
                course_dict["role"] = role  # Add user's role to the course dictionary

                if role == group_role_learner:
                    course_dict["cohort_id"] = course_to_cohort[course_id]

                courses.append(course_dict)

        return courses


async def get_user_org_cohorts(user_id: int, org_id: int) -> List[UserCohort]:
    """
    Get all the cohorts in the organization that the user is a member in
    """
    cohorts = await execute_db_operation(
        f"""SELECT c.id, c.name, uc.role
            FROM {cohorts_table_name} c
            JOIN {user_cohorts_table_name} uc ON c.id = uc.cohort_id
            WHERE uc.user_id = ? AND c.org_id = ?""",
        (user_id, org_id),
        fetch_all=True,
    )

    if not cohorts:
        return []

    return [
        {
            "id": cohort[0],
            "name": cohort[1],
            "role": cohort[2],
        }
        for cohort in cohorts
    ]


async def drop_task_completions_table():
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(f"DROP TABLE IF EXISTS {task_completions_table_name}")

        await conn.commit()


async def get_all_scorecards_for_org(org_id: int) -> List[Dict]:
    scorecards = await execute_db_operation(
        f"SELECT id, title, criteria FROM {scorecards_table_name} WHERE org_id = ?",
        (org_id,),
        fetch_all=True,
    )

    return [
        {
            "id": scorecard[0],
            "title": scorecard[1],
            "criteria": json.loads(scorecard[2]),
        }
        for scorecard in scorecards
    ]


async def undo_task_delete(task_id: int):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"UPDATE {tasks_table_name} SET deleted_at = NULL WHERE id = ?",
            (task_id,),
        )

        await conn.commit()


async def publish_scheduled_tasks():
    """Publish all tasks whose scheduled time has arrived"""
    current_time = datetime.now()
    # Ensure we're using UTC time for consistency
    current_time = datetime.now(timezone.utc)

    # Get all tasks that should be published now
    tasks = await execute_db_operation(
        f"""
        UPDATE {tasks_table_name}
        SET scheduled_publish_at = NULL
        WHERE status = '{TaskStatus.PUBLISHED}'
        AND scheduled_publish_at IS NOT NULL AND deleted_at IS NULL
        AND scheduled_publish_at <= ?
        RETURNING id
        """,
        (current_time,),
        fetch_all=True,
    )

    return [task[0] for task in tasks] if tasks else []


async def migrate_tasks_table():
    """Add scheduled_publish_at column if it doesn't exist"""
    columns = await execute_db_operation(
        f"PRAGMA table_info({tasks_table_name})",
        fetch_all=True,
    )

    columns_names = [column[1] for column in columns]
    if "scheduled_publish_at" not in columns_names:
        await execute_db_operation(
            f"ALTER TABLE {tasks_table_name} ADD COLUMN scheduled_publish_at DATETIME"
        )


async def add_generated_learning_material(task_id: int, task_details: Dict):
    await publish_learning_material_task(
        task_id,
        task_details["name"],
        convert_blocks_to_right_format(task_details["details"]["blocks"]),
        None,
        TaskStatus.PUBLISHED,  # TEMP: turn to draft later
    )


async def add_generated_quiz(task_id: int, task_details: Dict):
    current_scorecard_index = 0

    for question in task_details["details"]["questions"]:
        question["type"] = question.pop("question_type")

        question["blocks"] = convert_blocks_to_right_format(question["blocks"])

        question["answer"] = (
            convert_blocks_to_right_format(question["correct_answer"])
            if question.get("correct_answer")
            else None
        )
        question["input_type"] = (
            question.pop("answer_type") if question.get("answer_type") else "text"
        )
        question["response_type"] = (
            TaskAIResponseType.CHAT
            if question["type"] != QuestionType.OPEN_ENDED
            else TaskAIResponseType.REPORT
        )
        question["generation_model"] = None
        question["context"] = (
            {
                "blocks": prepare_blocks_for_publish(
                    convert_blocks_to_right_format(question["context"])
                ),
                "linkedMaterialIds": None,
            }
            if question.get("context")
            else None
        )
        question["max_attempts"] = 1 if task_details["type"] == TaskType.EXAM else None
        question["is_feedback_shown"] = (
            True if task_details["type"] == TaskType.QUIZ else False
        )
        if question.get("scorecard"):
            question["scorecard"]["id"] = current_scorecard_index
            current_scorecard_index += 1
        else:
            question["scorecard"] = None
        question["scorecard_id"] = None
        question["coding_languages"] = question.get("coding_languages", None)

    await publish_quiz(
        task_id,
        task_details["name"],
        task_details["details"]["questions"],
        None,
        TaskStatus.PUBLISHED,  # TEMP: turn to draft later
    )


def convert_content_to_blocks(content: str) -> List[Dict]:
    lines = content.split("\n")
    blocks = []
    for line in lines:
        blocks.append(
            {
                "type": "paragraph",
                "props": {
                    "textColor": "default",
                    "backgroundColor": "default",
                    "textAlignment": "left",
                },
                "content": [{"type": "text", "text": line, "styles": {}}],
                "children": [],
            }
        )

    return blocks


def convert_blocks_to_right_format(blocks: List[Dict]) -> List[Dict]:
    for block in blocks:
        for content in block["content"]:
            content["type"] = "text"
            if "styles" not in content:
                content["styles"] = {}

    return blocks


# async def add_generated_course(course_id: int, course_details: Dict):
#     await update_course_name(course_id, course_details["name"])

#     module_ids = await add_generated_course_modules(
#         course_id, course_details["modules"]
#     )

#     for index, module in enumerate(course_details["modules"]):
#         for concept in module["concepts"]:
#             for task in concept["tasks"]:
#                 if "details" not in task:
#                     continue

#                 task_id = await create_draft_task_for_course(
#                     task["name"],
#                     task["type"],
#                     course_id,
#                     module_ids[index],
#                 )

#                 if task["type"] == TaskType.LEARNING_MATERIAL:
#                     await add_generated_learning_material(task_id, task)
#                 else:
#                     await add_generated_quiz(task_id, task)


async def migrate_learning_material(task_id: int, task_details: Dict):
    await publish_learning_material_task(
        task_id,
        task_details["name"],
        task_details["blocks"],
        None,
        TaskStatus.PUBLISHED,  # TEMP: turn to draft later
    )


async def migrate_quiz(task_id: int, task_details: Dict):
    scorecards = []

    question = {}

    question["type"] = (
        QuestionType.OPEN_ENDED
        if task_details["response_type"] == "report"
        else (
            QuestionType.CODING
            if task_details["input_type"] == "coding"
            else QuestionType.OBJECTIVE
        )
    )

    question["blocks"] = task_details["blocks"]

    question["answer"] = (
        convert_content_to_blocks(task_details["answer"])
        if task_details.get("answer")
        else None
    )
    question["input_type"] = (
        "audio" if task_details["input_type"] == "audio" else "text"
    )
    question["response_type"] = (
        TaskAIResponseType.CHAT
        if question["type"] != QuestionType.OPEN_ENDED
        else TaskAIResponseType.REPORT
    )
    question["coding_languages"] = task_details.get("coding_language", None)
    question["generation_model"] = None
    question["context"] = (
        {
            "blocks": prepare_blocks_for_publish(
                convert_content_to_blocks(task_details["context"])
            ),
            "linkedMaterialIds": None,
        }
        if task_details.get("context")
        else None
    )
    question["max_attempts"] = (
        1 if task_details["response_type"] == TaskType.EXAM else None
    )
    question["is_feedback_shown"] = (
        False if task_details["response_type"] == TaskType.EXAM else True
    )

    if task_details["response_type"] == "report":
        scoring_criteria = task_details["scoring_criteria"]

        scorecard_criteria = []

        for criterion in scoring_criteria:
            scorecard_criteria.append(
                {
                    "name": criterion["category"],
                    "description": criterion["description"],
                    "min_score": criterion["range"][0],
                    "max_score": criterion["range"][1],
                }
            )

        is_new_scorecard = True
        scorecard_id = None
        for index, existing_scorecard in enumerate(scorecards):
            if existing_scorecard == scorecard_criteria:
                is_new_scorecard = False
                scorecard_id = index
                break

        question["scorecard"] = {
            "id": len(scorecards) if is_new_scorecard else scorecard_id,
            "title": "Scorecard",
            "criteria": scorecard_criteria,
        }

        if is_new_scorecard:
            scorecards.append(scorecard_criteria)
    else:
        question["scorecard"] = None

    question["scorecard_id"] = None

    await publish_quiz(
        task_id,
        task_details["name"],
        [question],
        None,
        TaskStatus.PUBLISHED,  # TEMP: turn to draft later
    )


async def add_course_modules(course_id: int, modules: List[Dict]):
    import random

    module_ids = []
    for module in modules:
        color = random.choice(
            [
                "#2d3748",  # Slate blue
                "#433c4c",  # Deep purple
                "#4a5568",  # Cool gray
                "#312e51",  # Indigo
                "#364135",  # Forest green
                "#4c393a",  # Burgundy
                "#334155",  # Navy blue
                "#553c2d",  # Rust brown
                "#37303f",  # Plum
                "#3c4b64",  # Steel blue
                "#463c46",  # Mauve
                "#3c322d",  # Coffee
            ]
        )
        module_id, _ = await add_milestone_to_course(course_id, module["name"], color)
        module_ids.append(module_id)

    return module_ids


async def migrate_course(course_id: int, course_details: Dict):
    await update_course_name(course_id, course_details["name"])

    module_ids = await add_course_modules(course_id, course_details["milestones"])

    for index, milestone in enumerate(course_details["milestones"]):
        for task in milestone["tasks"]:
            if task["type"] == "reading_material":
                task["type"] = str(TaskType.LEARNING_MATERIAL)
            else:
                if task["response_type"] == "exam":
                    task["type"] = str(TaskType.EXAM)
                else:
                    task["type"] = str(TaskType.QUIZ)

            task_id, _ = await create_draft_task_for_course(
                task["name"],
                task["type"],
                course_id,
                module_ids[index],
            )

            if task["type"] == TaskType.LEARNING_MATERIAL:
                await migrate_learning_material(task_id, task)
            else:
                await migrate_quiz(task_id, task)


def convert_task_description_to_blocks(course_details: Dict):
    for milestone in course_details["milestones"]:
        for task in milestone["tasks"]:
            task["blocks"] = convert_content_to_blocks(task["description"])

    return course_details


async def migrate_task_description_to_blocks(course_details: Dict):
    from api.routes.ai import migrate_content_to_blocks
    from api.utils.concurrency import async_batch_gather

    coroutines = []

    for milestone in course_details["milestones"]:
        for task in milestone["tasks"]:
            coroutines.append(migrate_content_to_blocks(task["description"]))
        #     break
        # break

    results = await async_batch_gather(coroutines)

    current_index = 0
    for milestone in course_details["milestones"]:
        for task in milestone["tasks"]:
            task["blocks"] = results[current_index]
            current_index += 1
        #     break
        # break

    return course_details


async def transfer_course_to_org(course_id: int, org_id: int):
    await execute_db_operation(
        f"UPDATE {courses_table_name} SET org_id = ? WHERE id = ?",
        (org_id, course_id),
    )


async def store_course_generation_request(course_id: int, job_details: Dict) -> str:
    job_uuid = str(uuid.uuid4())

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"INSERT INTO {course_generation_jobs_table_name} (uuid, course_id, status, job_details) VALUES (?, ?, ?, ?)",
            (
                job_uuid,
                course_id,
                str(GenerateCourseJobStatus.STARTED),
                json.dumps(job_details),
            ),
        )

        await conn.commit()

    return job_uuid


async def get_course_generation_job_details(job_uuid: str) -> Dict:
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"SELECT job_details FROM {course_generation_jobs_table_name} WHERE uuid = ?",
            (job_uuid,),
        )

        job = await cursor.fetchone()

        if job is None:
            raise ValueError("Job not found")

        return json.loads(job[0])


class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


async def update_course_generation_job_status_and_details(
    job_uuid: str, status: GenerateCourseJobStatus, details: Dict
):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"UPDATE {course_generation_jobs_table_name} SET status = ?, job_details = ? WHERE uuid = ?",
            (str(status), json.dumps(details, cls=EnumEncoder), job_uuid),
        )

        await conn.commit()


async def update_course_generation_job_status(
    job_uuid: str, status: GenerateCourseJobStatus
):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"UPDATE {course_generation_jobs_table_name} SET status = ? WHERE uuid = ?",
            (str(status), job_uuid),
        )

        await conn.commit()


async def store_task_generation_request(
    task_id: int, course_id: int, job_details: Dict
) -> str:
    job_uuid = str(uuid.uuid4())

    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"INSERT INTO {task_generation_jobs_table_name} (uuid, task_id, course_id, status, job_details) VALUES (?, ?, ?, ?, ?)",
            (
                job_uuid,
                task_id,
                course_id,
                str(GenerateTaskJobStatus.STARTED),
                json.dumps(job_details),
            ),
        )

        await conn.commit()

    return job_uuid


async def update_task_generation_job_status(
    job_uuid: str, status: GenerateTaskJobStatus
):
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"UPDATE {task_generation_jobs_table_name} SET status = ? WHERE uuid = ?",
            (str(status), job_uuid),
        )

        await conn.commit()


async def get_course_task_generation_jobs_status(course_id: int) -> List[str]:
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"SELECT status FROM {task_generation_jobs_table_name} WHERE course_id = ?",
            (course_id,),
        )

        statuses = [row[0] for row in await cursor.fetchall()]

        return {
            str(GenerateTaskJobStatus.COMPLETED): statuses.count(
                str(GenerateTaskJobStatus.COMPLETED)
            ),
            str(GenerateTaskJobStatus.STARTED): statuses.count(
                str(GenerateTaskJobStatus.STARTED)
            ),
        }


async def get_all_pending_task_generation_jobs() -> List[Dict]:
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"SELECT uuid, job_details FROM {task_generation_jobs_table_name} WHERE status = ?",
            (str(GenerateTaskJobStatus.STARTED),),
        )

        return [
            {
                "uuid": row[0],
                "job_details": json.loads(row[1]),
            }
            for row in await cursor.fetchall()
        ]


async def get_all_pending_course_structure_generation_jobs() -> List[Dict]:
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(
            f"SELECT uuid, course_id, job_details FROM {course_generation_jobs_table_name} WHERE status = ?",
            (str(GenerateCourseJobStatus.STARTED),),
        )

        return [
            {
                "uuid": row[0],
                "course_id": row[1],
                "job_details": json.loads(row[2]),
            }
            for row in await cursor.fetchall()
        ]


async def drop_task_generation_jobs_table():
    async with get_new_db_connection() as conn:
        cursor = await conn.cursor()

        await cursor.execute(f"DROP TABLE IF EXISTS {task_generation_jobs_table_name}")
