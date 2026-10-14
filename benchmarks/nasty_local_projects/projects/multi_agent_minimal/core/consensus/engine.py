async def run_consensus(task):
    responses = []
    for agent in task.agents:
        responses.append(await agent.run(task.payload))
    return {"consensus": responses[0] if responses else None, "responses": responses}
