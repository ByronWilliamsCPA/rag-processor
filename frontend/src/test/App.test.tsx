import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

// Mock the components to avoid complex dependencies in tests
vi.mock('@/components/ApiStatus', () => ({
  ApiStatus: () => <div data-testid="api-status">API Status Mock</div>,
}))

vi.mock('@/components/Header', () => ({
  Header: () => <header data-testid="header">Header Mock</header>,
}))

vi.mock('@/components/FileUpload', () => ({
  FileUpload: () => <div data-testid="file-upload">File Upload Mock</div>,
}))

vi.mock('@/components/UploadButton', () => ({
  UploadButton: () => <button data-testid="upload-button">Upload Button Mock</button>,
}))

describe('App', () => {
  it('renders the page title', () => {
    render(<App />)
    expect(screen.getByText('RAG Pipeline Ingestion')).toBeInTheDocument()
  })

  it('renders the page description', () => {
    render(<App />)
    expect(screen.getByText('Upload and process documents for your RAG pipeline')).toBeInTheDocument()
  })

  it('renders the header component', () => {
    render(<App />)
    expect(screen.getByTestId('header')).toBeInTheDocument()
  })

  it('renders the file upload component', () => {
    render(<App />)
    expect(screen.getByTestId('file-upload')).toBeInTheDocument()
  })

  it('renders the upload button component', () => {
    render(<App />)
    expect(screen.getByTestId('upload-button')).toBeInTheDocument()
  })

  it('renders the API status component', () => {
    render(<App />)
    expect(screen.getByTestId('api-status')).toBeInTheDocument()
  })

  it('renders footer with technology links', () => {
    render(<App />)
    expect(screen.getByText('Vite')).toBeInTheDocument()
    expect(screen.getByText('React')).toBeInTheDocument()
    expect(screen.getByText('FastAPI')).toBeInTheDocument()
  })
})
