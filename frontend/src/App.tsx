import './App.css'
import { Header } from '@/components/Header'
import { ApiStatus } from '@/components/ApiStatus'

function App() {
  return (
    <div className="app">
      <Header />

      <main className="app-main">
        <section className="hero-section">
          <h2>RAG Pipeline Ingestion</h2>
          <p>Upload and process documents for your RAG pipeline</p>
        </section>

        <section className="api-section">
          <h3>Backend API Status</h3>
          <ApiStatus />
        </section>
      </main>

      <footer className="app-footer">
        <p>
          Built with{' '}
          <a href="https://vite.dev" target="_blank" rel="noopener noreferrer">
            Vite
          </a>
          {' + '}
          <a href="https://react.dev" target="_blank" rel="noopener noreferrer">
            React
          </a>
          {' + '}
          <a href="https://fastapi.tiangolo.com" target="_blank" rel="noopener noreferrer">
            FastAPI
          </a>
        </p>
      </footer>
    </div>
  )
}

export default App
