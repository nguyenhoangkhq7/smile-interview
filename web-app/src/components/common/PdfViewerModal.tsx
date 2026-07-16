import React, { useState } from 'react';
import { X, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';

// Set up the PDF.js worker using unpkg CDN matching the installed version
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  pdfUrl: string;
  title?: string;
}

export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  isOpen,
  onClose,
  pdfUrl,
  title = 'Xem tài liệu PDF',
}) => {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [loading, setLoading] = useState<boolean>(true);

  if (!isOpen) return null;

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(1);
    setLoading(false);
  }

  function changePage(offset: number) {
    setPageNumber((prevPageNumber) => {
      const target = prevPageNumber + offset;
      if (numPages && target >= 1 && target <= numPages) {
        return target;
      }
      return prevPageNumber;
    });
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        padding: '1.5rem',
        animation: 'fadeIn 0.2s ease-out',
      }}
      onClick={onClose}
    >
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateY(16px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .pdf-scroll-container::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .pdf-scroll-container::-webkit-scrollbar-track {
          background: #f1f5f9;
        }
        .pdf-scroll-container::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 4px;
        }
        .pdf-scroll-container::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
      `}</style>
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '1rem',
          width: '100%',
          maxWidth: '900px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          animation: 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#f8fafc',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: '#0f172a' }}>
              {title}
            </h3>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.8rem',
                fontWeight: 500,
                color: '#475569',
                textDecoration: 'none',
                padding: '0.45rem 0.85rem',
                borderRadius: '0.5rem',
                border: '1px solid #cbd5e1',
                backgroundColor: '#ffffff',
                transition: 'all 0.15s ease',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f1f5f9';
                e.currentTarget.style.borderColor = '#94a3b8';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#ffffff';
                e.currentTarget.style.borderColor = '#cbd5e1';
              }}
            >
              <ExternalLink size={14} />
              Mở tab mới
            </a>
            <button
              onClick={onClose}
              style={{
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.45rem',
                borderRadius: '0.5rem',
                backgroundColor: '#e2e8f0',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#cbd5e1';
                e.currentTarget.style.color = '#334155';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#e2e8f0';
                e.currentTarget.style.color = '#64748b';
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Toolbar controls */}
        <div
          style={{
            padding: '0.5rem 1rem',
            borderBottom: '1px solid #e2e8f0',
            backgroundColor: '#f1f5f9',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
          }}
        >
          {/* Zoom controls */}
          <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
            <button
              disabled={scale <= 0.5}
              onClick={() => setScale((prev) => Math.max(0.5, prev - 0.1))}
              style={{
                background: '#ffffff',
                padding: '0.35rem 0.6rem',
                borderRadius: '0.375rem',
                cursor: scale <= 0.5 ? 'not-allowed' : 'pointer',
                opacity: scale <= 0.5 ? 0.5 : 1,
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ZoomOut size={14} />
            </button>
            <span style={{ fontSize: '0.8rem', minWidth: '3.5rem', textAlign: 'center', fontWeight: 500, color: '#334155' }}>
              {Math.round(scale * 100)}%
            </span>
            <button
              disabled={scale >= 2.0}
              onClick={() => setScale((prev) => Math.min(2.0, prev + 0.1))}
              style={{
                background: '#ffffff',
                padding: '0.35rem 0.6rem',
                borderRadius: '0.375rem',
                cursor: scale >= 2.0 ? 'not-allowed' : 'pointer',
                opacity: scale >= 2.0 ? 0.5 : 1,
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ZoomIn size={14} />
            </button>
          </div>

          {/* Navigation controls */}
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              disabled={pageNumber <= 1}
              onClick={() => changePage(-1)}
              style={{
                background: '#ffffff',
                padding: '0.35rem 0.6rem',
                borderRadius: '0.375rem',
                cursor: pageNumber <= 1 ? 'not-allowed' : 'pointer',
                opacity: pageNumber <= 1 ? 0.5 : 1,
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.78rem',
              }}
            >
              <ChevronLeft size={14} />
              Trước
            </button>
            <span style={{ fontSize: '0.8rem', color: '#334155', fontWeight: 500 }}>
              Trang {pageNumber} / {numPages || '-'}
            </span>
            <button
              disabled={numPages ? pageNumber >= numPages : true}
              onClick={() => changePage(1)}
              style={{
                background: '#ffffff',
                padding: '0.35rem 0.6rem',
                borderRadius: '0.375rem',
                cursor: numPages ? (pageNumber >= numPages ? 'not-allowed' : 'pointer') : 'not-allowed',
                opacity: numPages ? (pageNumber >= numPages ? 0.5 : 1) : 0.5,
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.78rem',
              }}
            >
              Sau
              <ChevronRight size={14} />
            </button>
          </div>
        </div>

        {/* PDF canvas viewer */}
        <div
          className="pdf-scroll-container"
          style={{
            flex: 1,
            backgroundColor: '#475569',
            overflow: 'auto',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            padding: '1.5rem',
          }}
        >
          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#ffffff', gap: '0.5rem' }}>
              <div style={{
                width: '32px',
                height: '32px',
                border: '3px solid rgba(255,255,255,0.3)',
                borderTopColor: '#ffffff',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
              <p style={{ fontSize: '0.85rem', margin: 0 }}>Đang nạp tài liệu PDF...</p>
              <style>{`
                @keyframes spin {
                  to { transform: rotate(360deg); }
                }
              `}</style>
            </div>
          )}
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={(err) => {
              console.error('react-pdf Load Error:', err);
              setLoading(false);
            }}
            loading=""
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderAnnotationLayer={false}
              renderTextLayer={false}
              loading=""
            />
          </Document>
        </div>
      </div>
    </div>
  );
};

export default PdfViewerModal;
