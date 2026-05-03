# docker compose -f deploy/local/docker-compose.yml exec api python -c "
# import asyncio
# from app.db.session import init_db, get_db
# from app.db.models import User
# import bcrypt

# async def create_user():
#     await init_db()
#     async for db in get_db():
#         pwd = bcrypt.hashpw(b'password123', bcrypt.gensalt()).decode()
#         user = User(email='test@example.com', hashed_password=pwd)
#         db.add(user)
#         await db.commit()
#         print(f'Created user: {user.id}')

# asyncio.run(create_user())
# "

# curl -X PUT http://localhost:8080/api/v1/settings/openrouter-key \
#   -H "Content-Type: application/json" \
#   -d "{\"api_key\": \"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\"}"

docker compose -f deploy/local/docker-compose.yml exec `
  -e OPENROUTER_CONTRACT_TESTS=true `
  api pytest tests/test_openrouter_contract.py -v