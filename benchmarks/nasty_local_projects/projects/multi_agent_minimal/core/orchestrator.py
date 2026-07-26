async def orchestrate_group(group_manager, task):
    return await group_manager.run(task)
