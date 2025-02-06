from database.session import Base, engine
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)