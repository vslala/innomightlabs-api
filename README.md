# InnoMightLabs API

A modern, cloud-native API service built with FastAPI, SQLAlchemy, and AWS Lambda, implementing Domain-Driven Design principles for building scalable and maintainable applications.

## Design Philosophy

InnoMightLabs API follows Domain-Driven Design (DDD) principles to create a clean, maintainable, and scalable architecture. The key aspects of our design philosophy include:

### Domain-Driven Design

- **Bounded Contexts**: The application is organized into distinct domains (user, conversation, chatbot) with clear boundaries.
- **Entities and Value Objects**: Core domain models are represented as entities with their own identity and lifecycle.
- **Repositories**: Data access is abstracted through repository interfaces that handle persistence concerns.
- **Services**: Business logic is encapsulated in service classes that operate on domain entities.

### Hexagonal Architecture

- **Core Domain Logic**: Isolated from external concerns like databases and APIs.
- **Adapters**: Controllers and repositories act as adapters between the core domain and external systems.
- **Ports**: Interfaces define how the application interacts with external systems.

### Clean Code Principles

- **Single Responsibility**: Each class has a single responsibility and reason to change.
- **Dependency Injection**: Dependencies are injected rather than created within components.
- **Separation of Concerns**: Clear separation between domain logic, application services, and infrastructure.

## Code Structure

```
innomightlabs-api/
├── app/                      # Application source code
│   ├── chatbot/              # Chatbot domain
│   │   ├── workflows/        # Chatbot workflow implementations
│   │   ├── chatbot_models.py # Data models for chatbot
│   │   └── ...
│   ├── common/               # Shared components and utilities
│   │   ├── config.py         # Application configuration
│   │   ├── controller.py     # Base controller class
│   │   ├── db_connect.py     # Database connection management
│   │   ├── entities.py       # Base entity classes
│   │   └── ...
│   ├── conversation/         # Conversation domain
│   │   ├── messages/         # Message subdomain
│   │   └── ...
│   ├── user/                 # User domain
│   └── main.py               # Application entry point
├── infra/                    # Infrastructure as Code (Terraform)
│   ├── lambdas/              # Lambda function definitions
│   ├── main.tf               # Main Terraform configuration
│   └── ...
├── migrations/               # Database migration scripts
│   ├── raw_sql/              # Raw SQL migration scripts
│   └── versions/             # Alembic migration versions
└── tests/                    # Test suite
    └── unit/                 # Unit tests
```

## Getting Started with Local Development

### Prerequisites

- Python 3.13+
- Docker and Docker Compose
- AWS CLI configured with appropriate credentials
- UV package manager (`pip install uv`)

### Step 1: Clone the Repository

```bash
git clone https://github.com/innomightlabs/innomightlabs-api.git
cd innomightlabs-api
```

### Step 2: Set Up Environment Variables

Create a `.envrc` file in the project root with the following variables:

```bash
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password
export POSTGRES_DB=innomightlabs
export STAGE=local
export AWS_PROFILE=your_aws_profile  # Only needed for local development
```

If you're using direnv, run:

```bash
direnv allow
```

Otherwise, source the file:

```bash
source .envrc
```

### Step 3: Start the Database

```bash
docker-compose up -d db
```

### Step 4: Install Dependencies

```bash
uv pip install --system .
```

### Step 5: Run Database Migrations

```bash
alembic upgrade head
```

### Step 6: Start the API Server

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000. You can access the Swagger UI documentation at http://localhost:8000/docs.

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment. The workflow is defined in `.github/workflows/ci.yml` and includes the following stages:

### Build Stage

- Checks out the code
- Sets up Python 3.13
- Installs dependencies using UV
- Runs linting with Ruff

### Test Stage

- Sets up a PostgreSQL database using Docker Compose
- Runs database migrations
- Starts the FastAPI application
- Performs health checks

### Deploy Stage (only on main branch)

- Builds and pushes a Docker image to Amazon ECR
- Deploys infrastructure using Terraform
- Runs database migrations in the deployed environment
- Outputs the API Gateway URL

## Contributing

### Prerequisites

- Python 3.13+
- UV package manager
- Docker and Docker Compose

### Setup Development Environment

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/innomightlabs-api.git
   ```
3. Set up environment variables as described in the "Getting Started" section
4. Install dependencies:
   ```bash
   uv pip install --system .
   ```
5. Install development dependencies:
   ```bash
   uv pip install --system .[dev]
   ```

### Development Workflow

1. Create a new branch for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Run linting:
   ```bash
   ruff check .
   ```
4. Run tests:
   ```bash
   pytest
   ```
5. Commit your changes:
   ```bash
   git commit -m "Add your feature description"
   ```
6. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
7. Create a pull request to the `dev` branch of the main repository

### Code Style Guidelines

- Follow PEP 8 guidelines
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions small and focused on a single responsibility
- Use meaningful variable and function names