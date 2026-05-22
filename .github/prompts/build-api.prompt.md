---
name: build-api
description: Generate a FastAPI endpoint with proper models and structure
agent: implementation
tools: ['edit', 'terminal']
argument-hint: endpoint=Endpoint name, purpose=Short description
---

You are implementing a FastAPI endpoint for crypt.ml.

Endpoint name:
${input:endpoint}

Purpose:
${input:purpose}

Requirements:

1. Define Pydantic request model
2. Define Pydantic response model
3. Include type hints everywhere
4. Include error handling
5. Return structured JSON
6. Keep business logic separated (service layer pattern)

Follow this structure:

- schemas.py (if needed)
- services/logic file
- main router integration

Add minimal comments explaining important logic.

Avoid overengineering.
Avoid unnecessary abstractions.
Write clean, production-ready Python.
