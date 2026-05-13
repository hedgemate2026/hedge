/**
 * Monte Carlo Simulation Engine
 * Ported from Python implementation for HedgeMate.
 */

// Math helpers
export const mean = (data) => data.length ? data.reduce((a, b) => a + b, 0) / data.length : 0;
export const stdev = (data) => {
  if (data.length < 2) return 0;
  const m = mean(data);
  return Math.sqrt(data.reduce((a, b) => a + Math.pow(b - m, 2), 0) / (data.length - 1));
};
export const covariance = (x, y) => {
  if (x.length !== y.length || x.length < 2) return 0;
  const mx = mean(x);
  const my = mean(y);
  let sum = 0;
  for (let i = 0; i < x.length; i++) {
    sum += (x[i] - mx) * (y[i] - my);
  }
  return sum / (x.length - 1);
};
export const correlation = (x, y) => {
  const cov = covariance(x, y);
  const sx = stdev(x);
  const sy = stdev(y);
  return sx && sy ? cov / (sx * sy) : 0;
};
export const percentile = (data, p) => {
  if (!data.length) return 0;
  const s = [...data].sort((a, b) => a - b);
  const idx = Math.floor(s.length * p);
  return s[Math.max(0, Math.min(idx, s.length - 1))];
};

// Cholesky Decomposition
export const choleskyDecomposition = (matrix) => {
  const n = matrix.length;
  const L = Array.from({ length: n }, () => Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let sum = 0;
      for (let k = 0; k < j; k++) {
        sum += L[i][k] * L[j][k];
      }
      if (i === j) {
        const val = matrix[i][i] - sum;
        L[i][j] = val > 0 ? Math.sqrt(val) : 1e-9; // Avoid zero for stability
      } else {
        L[i][j] = L[j][j] > 0 ? (matrix[i][j] - sum) / L[j][j] : 0;
      }
    }
  }
  return L;
};

// Covariance Matrix
export const buildCovarianceMatrix = (returnsMatrix) => {
  const nAssets = returnsMatrix.length;
  const covMatrix = Array.from({ length: nAssets }, () => Array(nAssets).fill(0));
  for (let i = 0; i < nAssets; i++) {
    for (let j = i; j < nAssets; j++) {
      const cov = covariance(returnsMatrix[i], returnsMatrix[j]);
      covMatrix[i][j] = cov;
      covMatrix[j][i] = cov;
    }
  }
  return covMatrix;
};

// Random Normal (Box-Muller)
const randomGauss = (m = 0, s = 1) => {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return m + s * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
};

// Multi-variate Path Simulation (Optimised GBM)
export const simulateMultivariatePaths = (means, L, nSimulations = 200, horizon = 63) => {
  const nAssets = means.length;
  const varPerAsset = Array(nAssets).fill(0);
  for (let i = 0; i < nAssets; i++) {
    for (let k = 0; k <= i; k++) {
      varPerAsset[i] += Math.pow(L[i][k], 2);
    }
  }

  const sqrtH = Math.sqrt(horizon);
  const scaledDrifts = means.map((m, i) => (m - 0.5 * varPerAsset[i]) * horizon);
  const scaledL = L.map(row => row.map(val => val * sqrtH));

  const finalReturns = [];
  for (let s = 0; s < nSimulations; s++) {
    const z = Array.from({ length: nAssets }, () => randomGauss());
    const rowResults = [];
    for (let i = 0; i < nAssets; i++) {
      let sumLz = 0;
      for (let j = 0; j <= i; j++) {
        sumLz += scaledL[i][j] * z[j];
      }
      rowResults.push(Math.exp(scaledDrifts[i] + sumLz) - 1.0);
    }
    finalReturns.push(rowResults);
  }
  return finalReturns;
};

// Multi-objective Sharpe Ratio
export const computeMultiobjectiveSharpe = (
  annReturn,
  riskFreeAnnual,
  annVol,
  cvar95,
  mdd,
  crisisWeight = 0.0
) => {
  const excess = annReturn - riskFreeAnnual;
  const sharpeStd = annVol > 0 ? excess / annVol : 0;
  const sharpeCvar = cvar95 < 0 ? excess / (-cvar95) : 0;
  const sharpeMdd = mdd < 0 ? excess / (-mdd) : 0;

  const cw = Math.max(0, Math.min(1, crisisWeight));
  const wStd = 0.40 * (1.0 - cw) + 0.10 * cw;
  const wCvar = 0.35 * (1.0 - cw) + 0.45 * cw;
  const wMdd = 0.25 * (1.0 - cw) + 0.45 * cw;

  const totalW = wStd + wCvar + wMdd;
  const moSharpe = (wStd * sharpeStd + wCvar * sharpeCvar + wMdd * sharpeMdd) / totalW;

  return {
    sharpeStd,
    sharpeCvar,
    sharpeMdd,
    moSharpe,
    weights: { std: wStd, cvar: wCvar, mdd: wMdd }
  };
};

// Macro Adjustments
export const adjustMeansForMacro = (baseMeans, shocks, returnsMatrix, macroReturnsMatrix) => {
  const { rate: rateShock, fx: fxShock, oil: oilShock } = shocks;
  const nAssets = baseMeans.length;

  if (!returnsMatrix || !macroReturnsMatrix || macroReturnsMatrix.length < 3) {
    const totalAdj = (-(rateShock / 10000) * 1.5 + (fxShock / 100) * 0.2 - (oilShock / 100) * 0.1) / 252;
    return baseMeans.map(m => m + totalAdj);
  }

  const rateRets = macroReturnsMatrix[0];
  const fxRets = macroReturnsMatrix[1];
  const oilRets = macroReturnsMatrix[2];

  const getBeta = (ys, xs) => {
    const cov = covariance(ys, xs);
    const varX = Math.pow(stdev(xs), 2);
    return varX ? cov / varX : 0;
  };

  const rateShift = -(rateShock / 10000) * 7.0;
  const fxShift = fxShock / 100;
  const oilShift = oilShock / 100;

  return baseMeans.map((m, i) => {
    const assetRets = returnsMatrix[i];
    const bRate = getBeta(assetRets, rateRets);
    const bFx = getBeta(assetRets, fxRets);
    const bOil = getBeta(assetRets, oilRets);
    const drift = (bRate * rateShift + bFx * fxShift + bOil * oilShift) / 252.0;
    return m + drift;
  });
};

export const adjustCorrForStress = (baseCorr, stressFactor) => {
  const n = baseCorr.length;
  const out = Array.from({ length: n }, () => Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      if (i === j) out[i][j] = 1.0;
      else {
        const c = baseCorr[i][j];
        const target = c >= 0 ? 0.80 : -0.20;
        out[i][j] = c + (target - c) * stressFactor * 0.55;
      }
    }
  }
  return out;
};

const VOL_MULTIPLIER = {
  equity: 2.5,
  bond_etf: 1.5,
  gold_etf: 2.0,
  crypto: 3.0,
  default: 2.2
};

export const adjustVolsForStress = (baseStds, stressFactor, assetClasses = []) => {
  return baseStds.map((std, i) => {
    const cls = (assetClasses[i] || 'default').toLowerCase();
    const mult = VOL_MULTIPLIER[cls] || VOL_MULTIPLIER.default;
    const scale = 1.0 + stressFactor * (mult - 1.0);
    return std * scale;
  });
};

// Main Simulation Runner
export const runMacroScenarioSimulation = (
  returnsMatrix,
  macroReturnsMatrix,
  shocks, // {rate, fx, oil}
  options = {}
) => {
  const { nSimulations = 200, horizon = 63, confLevel = 0.05, riskFreeRate = 0.02, weights } = options;
  const nAssets = returnsMatrix.length;
  if (nAssets === 0) return null;

  const portWeights = weights || Array(nAssets).fill(1 / nAssets);
  const baseMeans = returnsMatrix.map(r => mean(r));
  const baseCov = buildCovarianceMatrix(returnsMatrix);
  const baseStds = baseCov.map((row, i) => Math.sqrt(Math.max(row[i], 1e-12)));
  
  const baseCorr = Array.from({ length: nAssets }, () => Array(nAssets).fill(0));
  for (let i = 0; i < nAssets; i++) {
    for (let j = 0; j < nAssets; j++) {
      const denom = baseStds[i] * baseStds[j];
      baseCorr[i][j] = i === j ? 1.0 : (baseCov[i][j] / denom || 0);
    }
  }

  const stressFactor = (Math.min(Math.abs(shocks.rate) / 300, 1) + Math.min(Math.abs(shocks.fx) / 30, 1) + Math.min(Math.abs(shocks.oil) / 60, 1)) / 3.0;

  const shockedMeans = adjustMeansForMacro(baseMeans, shocks, returnsMatrix, macroReturnsMatrix);
  const stressedCorr = adjustCorrForStress(baseCorr, stressFactor);
  const stressedStds = adjustVolsForStress(baseStds, stressFactor);

  const stressedCov = Array.from({ length: nAssets }, () => Array(nAssets).fill(0));
  for (let i = 0; i < nAssets; i++) {
    for (let j = 0; j < nAssets; j++) {
      stressedCov[i][j] = stressedCorr[i][j] * stressedStds[i] * stressedStds[j];
    }
  }

  let L;
  try {
    L = choleskyDecomposition(stressedCov);
  } catch (e) {
    L = choleskyDecomposition(baseCov);
  }

  const simulated = simulateMultivariatePaths(shockedMeans, L, nSimulations, horizon);
  const portReturns = simulated.map(sim => sim.reduce((acc, val, idx) => acc + val * portWeights[idx], 0));

  const varThresh = percentile(portReturns, confLevel);
  const tail = portReturns.filter(r => r <= varThresh);
  const cvar = tail.length ? mean(tail) : varThresh;
  
  const sortedRets = [...portReturns].sort((a, b) => a - b);
  const mddApprox = mean(sortedRets.slice(0, Math.max(1, Math.floor(portReturns.length * confLevel))));

  // Annualize returns for Sharpe calculation
  // portReturns are cumulative returns over 'horizon' days
  const avgHorizonReturn = mean(portReturns);
  const annReturn = Math.pow(1 + Math.max(-0.99, avgHorizonReturn), 252 / horizon) - 1;
  const annVol = stdev(portReturns) * Math.sqrt(252 / horizon);
  
  const moSharpe = computeMultiobjectiveSharpe(annReturn, riskFreeRate, annVol, cvar, mddApprox, stressFactor);

  return {
    cvar,
    varThresh,
    mddApprox,
    stressFactor,
    moSharpe,
    assetExpectations: shockedMeans.map((m, i) => Math.exp(m * horizon) - 1),
    stressedCorr
  };
};
