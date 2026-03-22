# AI1stSEO Platform - UML System Design

## Overview
Interactive Mermaid diagrams showing the AI1stSEO platform architecture.

---

## System Architecture

```mermaid
flowchart TD
    User[User] --> Dashboard[Web Dashboard]
    Dashboard --> API[API Gateway]
    API --> Backend[Flask Backend]
    Backend --> SEO[SEO Analysis Engine]
    Backend --> DB[(Database)]
    SEO --> Results[Analysis Results]
```

## Use Case Diagram

```mermaid
flowchart LR
    FreeUser[Free User] --> Signup[Sign Up]
    FreeUser --> BasicAnalysis[Run Basic SEO]
    FreeUser --> ViewReport[View Report]
    
    PaidUser[Paid User] --> AdvAnalysis[Advanced Analysis]
    PaidUser --> AIAnalysis[AI SEO Analysis]
    PaidUser --> Export[Export Reports]
```

## Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant D as Dashboard
    participant A as API
    participant S as SEO Engine
    
    U->>D: Enter Website URL
    D->>A: POST /analyze
    A->>S: Run 170 SEO Checks
    S->>A: Return Results
    A->>D: Analysis Complete
    D->>U: Display Report
```

## Component Architecture

```mermaid
flowchart TB
    subgraph Frontend
        React[React App]
        UI[User Interface]
    end
    
    subgraph Backend
        Flask[Flask API]
        SEOEngine[SEO Analyzer]
    end
    
    subgraph Data
        PostgreSQL[(PostgreSQL)]
        Redis[(Redis Cache)]
    end
    
    React --> Flask
    Flask --> SEOEngine
    Flask --> PostgreSQL
    Flask --> Redis
```

## Deployment Architecture

```mermaid
flowchart LR
    Users[Users] --> CF[CloudFront CDN]
    CF --> AppRunner[AWS App Runner]
    AppRunner --> GitHub[GitHub Repo]
    AppRunner --> RDS[(RDS Database)]
```
