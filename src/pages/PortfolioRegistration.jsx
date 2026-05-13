import React, { useState, useRef, useCallback } from 'react';
import Tesseract from 'tesseract.js';
import { UploadCloud, Trash2, Shield, FileText, Image as ImageIcon, List, Plus, CheckCircle, X, ArrowRight, Briefcase, Loader2 } from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate } from 'react-router-dom';
import { usePortfolios } from '../context/PortfolioContext';
import { getTickerQuote } from '../services/yahooFinance';
import { debounce, ASSET_DATABASE } from '../utils/helpers';
import './PortfolioRegistration.css';

const TICKER_DB = ASSET_DATABASE;

export const PortfolioRegistration = () => {
  const navigate = useNavigate();
  const { addPortfolio } = usePortfolios();
  const fileInputRef = useRef(null);

  const [portfolioName, setPortfolioName] = useState('');
  const [purpose, setPurpose] = useState('장기 가치 투자');
  const [rows, setRows] = useState([
    { id: 1, ticker: '', name: '', qty: 0, cost: 0 },
  ]);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [createdPortfolio, setCreatedPortfolio] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [isOcrProcessing, setIsOcrProcessing] = useState(false);
  const [ocrProgress, setOcrProgress] = useState(0);
  const nextId = useRef(2);

  const addRow = () => {
    setRows(prev => [...prev, { id: nextId.current++, ticker: '', name: '', qty: 0, cost: 0 }]);
  };

  const removeRow = (id) => {
    if (rows.length <= 1) return; // keep at least one row
    setRows(prev => prev.filter(r => r.id !== id));
  };

  // Debounced ticker lookup
  const debouncedLookup = useCallback(
    debounce(async (id, ticker) => {
      const upper = ticker.toUpperCase();
      if (TICKER_DB[upper]) {
        setRows(prev => prev.map(r => r.id === id ? { 
          ...r, 
          name: TICKER_DB[upper].name, 
          cost: r.cost || TICKER_DB[upper].price 
        } : r));
      } else {
        const quote = await getTickerQuote(upper);
        if (quote) {
          setRows(prev => prev.map(r => {
            if (r.id === id && r.ticker.toUpperCase() === upper) {
              return { ...r, name: quote.name, cost: r.cost || quote.price };
            }
            return r;
          }));
        }
      }
    }, 500),
    []
  );

  const updateRow = (id, field, value) => {
    setRows(prev => prev.map(r => {
      if (r.id !== id) return r;
      return { ...r, [field]: value };
    }));

    if (field === 'ticker' && value.length >= 2) {
      debouncedLookup(id, value);
    }
  };

  const totalValue = rows.reduce((sum, r) => sum + (r.qty * r.cost), 0);

  const processOcr = async (file) => {
    setIsOcrProcessing(true);
    setOcrProgress(0);
    try {
      const result = await Tesseract.recognize(file, 'eng+kor', {
        logger: m => {
          if (m.status === 'recognizing text') {
            setOcrProgress(m.progress);
          }
        }
      });
      
      const text = result.data.text;
      console.log('Raw OCR Result:', text);
      const lines = text.split('\n');
      const parsedRows = [];
      
      lines.forEach(line => {
        const cleanLine = line.trim().replace(/,/g, '');
        if (!cleanLine) return;
        
        // Skip header lines
        if (cleanLine.toUpperCase().includes('TICKER') || cleanLine.toUpperCase().includes('QUANTITY') || cleanLine.toUpperCase().includes('티커')) return;

        // Extract all numeric values
        const numbers = cleanLine.match(/\d+(?:\.\d+)?/g);
        
        // Extract words
        const words = cleanLine.split(/\s+/);
        if (words.length > 0) {
          // Assume the first likely valid word is the ticker
          let maybeTicker = '';
          let tickerStartIdx = 0;
          for (let i = 0; i < words.length; i++) {
             let cleanWord = words[i].replace(/[^a-zA-Z.]/g, '').toUpperCase();
             // Remove any trailing/leading dots which are likely from numbering (e.g. "1.")
             cleanWord = cleanWord.replace(/^\.+|\.+$/g, '');
             
             // Must be 1-6 chars, MUST contain at least one letter
             if (/^[A-Z.]{1,6}$/.test(cleanWord) && /[A-Z]/.test(cleanWord) && cleanWord !== 'AVG' && cleanWord !== 'COST') {
               maybeTicker = cleanWord;
               break;
             }
             tickerStartIdx += words[i].length + 1;
          }

          if (maybeTicker && numbers && numbers.length >= 2) {
             const qty = parseFloat(numbers[numbers.length - 2]);
             const cost = parseFloat(numbers[numbers.length - 1]);
             
             // Extract optional name between ticker and the numbers
             const restOfStr = cleanLine.substring(tickerStartIdx + maybeTicker.length);
             const firstNumIdx = restOfStr.search(/\d/);
             let name = '';
             if (firstNumIdx !== -1) {
               name = restOfStr.substring(0, firstNumIdx).replace(/[^\w가-힣\s]/g, '').trim();
             }

             parsedRows.push({
               id: nextId.current++,
               ticker: maybeTicker,
               name: name || '',
               qty,
               cost,
             });
          }
        }
      });

      if (parsedRows.length > 0) {
        setRows(prev => {
          // If previous exists but only 1 empty row, replace
          const isDefault = prev.length === 1 && prev[0].ticker === '';
          return isDefault ? parsedRows : [...prev, ...parsedRows];
        });
      }
    } catch(err) {
      console.error(err);
      alert('이미지 분석 중 오류가 발생했습니다.');
    } finally {
      setIsOcrProcessing(false);
      setOcrProgress(0);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      processOcr(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      setUploadedFile(file);
      processOcr(file);
    } else if (file) {
      alert('이미지 파일만 업로드 가능합니다.');
    }
  };

  const handleSubmit = () => {
    if (!portfolioName.trim()) {
      alert('포트폴리오 이름을 입력해주세요.');
      return;
    }
    const validRows = rows.filter(r => r.ticker.trim());
    if (validRows.length === 0) {
      alert('최소 1개 이상의 종목을 입력해주세요.');
      return;
    }

    // Save to context (archived)
    const newPortfolio = addPortfolio({
      name: portfolioName,
      purpose,
      assets: validRows.map(r => ({
        ticker: r.ticker.toUpperCase(),
        name: r.name,
        qty: r.qty,
        cost: r.cost,
      })),
    });

    setCreatedPortfolio(newPortfolio);
    setShowSuccess(true);
  };

  const handleCancel = () => {
    setPortfolioName('');
    setPurpose('장기 가치 투자');
    setRows([{ id: nextId.current++, ticker: '', name: '', qty: 0, cost: 0 }]);
    setUploadedFile(null);
  };

  if (showSuccess && createdPortfolio) {
    return (
      <div className="portfolio-reg" style={{display:'flex',alignItems:'center',justifyContent:'center',minHeight:'60vh'}}>
        <div style={{textAlign:'center', maxWidth: '480px'}}>
          <div className="success-icon-wrapper">
            <CheckCircle size={56} className="text-accent-light" />
          </div>
          <h1 className="mt-4">포트폴리오가 등록되었습니다!</h1>
          <p className="text-secondary mt-2" style={{lineHeight: 1.6}}>
            포트폴리오가 <strong style={{color: 'var(--accent-light)'}}>내 포트폴리오</strong>에 아카이빙 되었습니다.<br />
            등록된 포트폴리오를 확인하고 분석을 시작하세요.
          </p>
          <div className="success-summary mt-6">
            <div className="card-box" style={{display:'inline-block',padding:'1.5rem 3rem',textAlign:'left'}}>
              <div className="text-sm text-secondary">포트폴리오</div>
              <div className="font-semibold mt-1">{createdPortfolio.name}</div>
              <div className="text-sm text-secondary mt-4">종목 수</div>
              <div className="font-semibold mt-1">{createdPortfolio.assets.length}개</div>
              <div className="text-sm text-secondary mt-4">총 투자금액</div>
              <div className="font-semibold mt-1 text-accent-light">₩{createdPortfolio.totalValue.toLocaleString()}</div>
              <div className="text-sm text-secondary mt-4">상태</div>
              <div className="font-semibold mt-1">
                <span className="status-badge-new">NEW — 분석 대기</span>
              </div>
            </div>
          </div>
          <div className="success-actions mt-6 flex gap-3 justify-center">
            <Button variant="secondary" onClick={() => {
              setShowSuccess(false);
              setCreatedPortfolio(null);
              handleCancel();
            }}>
              <Plus size={16} /> 추가 등록
            </Button>
            <Button variant="primary" onClick={() => navigate('/portfolios')}>
              <Briefcase size={16} /> 내 포트폴리오 보기 <ArrowRight size={14} />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="portfolio-reg">
      {/* Flow Breadcrumb */}
      <div className="flow-breadcrumb mb-6">
        <span className="flow-crumb active">
          <span className="crumb-step">1</span> 포트폴리오 등록
        </span>
        <span className="flow-arrow">→</span>
        <span className="flow-crumb">
          <span className="crumb-step">2</span> 내 포트폴리오
        </span>
        <span className="flow-arrow">→</span>
        <span className="flow-crumb">
          <span className="crumb-step">3</span> 분석 리포트
        </span>
      </div>

      <h1 className="mb-2">새 포트폴리오 생성</h1>
      <p className="text-secondary text-sm mb-8" style={{maxWidth: '600px', lineHeight: 1.6}}>
        HedgeMate의 정밀한 데이터 분석을 시작하세요. 자산을 업로드하거나 수동으로 입력하여 맞춤형 인사이트를 확보하십시오.
      </p>

      <div className="top-grid mb-6">
        {/* Card 1: Basic Info */}
        <div className="card-box">
          <div className="card-header">
            <span className="icon-wrapper"><Shield size={16}/></span>
            <span className="font-semibold">기본 정보</span>
          </div>
          <div className="form-group mt-6">
            <label>포트폴리오 이름</label>
            <input 
              type="text" 
              placeholder="예: 2024 하이테크 성장 주" 
              value={portfolioName}
              onChange={(e) => setPortfolioName(e.target.value)}
            />
          </div>
          <div className="form-group mt-6">
            <label>운용 목적</label>
            <select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              <option>장기 가치 투자</option>
              <option>단기 스윙</option>
              <option>리스크 헷지</option>
              <option>배당 수익</option>
              <option>성장주 집중</option>
            </select>
          </div>
          {portfolioName && (
            <div className="portfolio-preview mt-6">
              <div className="text-xs text-secondary">미리보기</div>
              <div className="text-sm font-semibold mt-1">{portfolioName}</div>
              <div className="text-xs text-secondary mt-1">{purpose} · {rows.filter(r=>r.ticker).length}종목</div>
            </div>
          )}
        </div>

        {/* Card 2: File Upload */}
        <div className="card-box">
          <div className="card-header justify-between">
            <div className="flex items-center gap-2">
              <span className="icon-wrapper"><ImageIcon size={16}/></span>
              <span className="font-semibold">이미지 등록 (OCR)</span>
            </div>
            <span className="badge">JPG / PNG SUPPORTED</span>
          </div>

          {uploadedFile ? (
            <div className="uploaded-file mt-6">
              <div className="flex items-center gap-3">
                {isOcrProcessing ? (
                  <Loader2 size={24} className="text-secondary rotate-animation" style={{animation: 'spin 2s linear infinite'}} />
                ) : (
                  <ImageIcon size={24} className="text-accent-light" />
                )}
                <div className="flex-1" style={{minWidth: 0}}>
                  <div className="text-sm font-medium" style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{uploadedFile.name}</div>
                  <div className="text-xs text-secondary">
                    {isOcrProcessing ? `AI 이미지 스캔 중... ${Math.round(ocrProgress * 100)}%` : `${(uploadedFile.size / 1024).toFixed(1)} KB`}
                  </div>
                </div>
                {!isOcrProcessing && (
                  <button onClick={() => setUploadedFile(null)} style={{color:'var(--text-secondary)'}}><X size={16}/></button>
                )}
              </div>
              <div className="upload-progress mt-4">
                <div 
                  className="upload-progress-fill" 
                  style={{ width: isOcrProcessing ? `${Math.max(10, ocrProgress * 100)}%` : '100%', transition: 'width 0.3s ease' }}
                ></div>
              </div>
              <div className="text-xs mt-2" style={{ color: isOcrProcessing ? 'var(--text-secondary)' : 'var(--accent-light)' }}>
                {isOcrProcessing ? '구조화된 테이블 데이터를 파싱 중입니다...' : '✓ 추출 완료! 아래 표에서 데이터를 확인/수정하세요.'}
              </div>
            </div>
          ) : (
            <div 
              className={`upload-area mt-6 ${dragOver ? 'drag-over' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <UploadCloud size={32} className="text-secondary mb-4" />
              <p className="font-medium">이미지를 드래그하거나 클릭하여 선택하세요</p>
              <p className="text-xs text-secondary mt-2">표 형태(티커, 수량, 단가)의 사진을 인식합니다</p>
            </div>
          )}
          <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept="image/*" style={{display:'none'}} />
        </div>
      </div>

      {/* Card 3: Manual Input */}
      <div className="card-box w-full mb-8">
        <div className="card-header justify-between">
          <div className="flex items-center gap-2">
            <span className="icon-wrapper"><List size={16}/></span>
            <span className="font-semibold">종목 수동 입력</span>
          </div>
          <button className="text-accent text-sm font-medium flex items-center gap-1" onClick={addRow}>
            <Plus size={14}/> 행 추가
          </button>
        </div>
        
        <table className="manual-table mt-6">
          <thead>
            <tr>
              <th>티커 (TICKER)</th>
              <th>종목명 (선택)</th>
              <th>수량 (QUANTITY)</th>
              <th>평균 단가 (AVG. COST)</th>
              <th>작업</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id}>
                <td>
                  <input 
                    type="text" 
                    value={row.ticker}
                    onChange={(e) => updateRow(row.id, 'ticker', e.target.value)}
                    placeholder="AAPL"
                  />
                </td>
                <td>
                  <input 
                    type="text" 
                    value={row.name}
                    onChange={(e) => updateRow(row.id, 'name', e.target.value)}
                    placeholder="종목명"
                  />
                </td>
                <td>
                  <input 
                    type="number" 
                    value={row.qty}
                    onChange={(e) => updateRow(row.id, 'qty', parseFloat(e.target.value) || 0)}
                    className="text-center" 
                  />
                </td>
                <td>
                  <input 
                    type="number" 
                    value={row.cost}
                    onChange={(e) => updateRow(row.id, 'cost', parseFloat(e.target.value) || 0)}
                    className="text-center" 
                    step="0.01"
                  />
                </td>
                <td>
                  <button className="trash-btn" onClick={() => removeRow(row.id)}>
                    <Trash2 size={16}/>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalValue > 0 && (
          <div className="total-bar mt-4 flex justify-between items-center">
            <span className="text-sm text-secondary">총 투자금액</span>
            <span className="text-lg font-bold text-accent-light">₩{totalValue.toLocaleString()}</span>
          </div>
        )}
      </div>

      <div className="actions flex justify-between items-center">
        <div className="text-sm text-secondary">
          {rows.filter(r=>r.ticker.trim()).length}개 종목 등록됨
        </div>
        <div className="flex gap-4 items-center">
          <Button variant="text" onClick={handleCancel}>취소</Button>
          <Button variant="primary" onClick={handleSubmit}>
            포트폴리오 등록 <ArrowRight size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
};
