/**
 * Carga e validacao da configuracao do operador.
 */

import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const VALID_POLICIES = ['most-positive', 'most-negative', 'neutral'];
const VALID_DIRECTIONS = ['auto', 'first', 'last'];

/**
 * Chaves que esta ferramenta deliberadamente nao suporta. Elas so fazem
 * sentido para contornar controle de resposta duplicada, o que esta fora do
 * escopo: uma execucao envia uma pesquisa, com a identidade de rede real da
 * maquina que rodou.
 */
const REJECTED = {
  proxy: 'rotacao de proxy/IP nao e suportada',
  proxies: 'rotacao de proxy/IP nao e suportada',
  proxyList: 'rotacao de proxy/IP nao e suportada',
  repeat: 'a ferramenta envia uma pesquisa por execucao',
  count: 'a ferramenta envia uma pesquisa por execucao',
  iterations: 'a ferramenta envia uma pesquisa por execucao',
  loop: 'a ferramenta envia uma pesquisa por execucao',
  concurrency: 'a ferramenta nao executa envios em paralelo',
  userAgents: 'troca de user-agent para mascarar origem nao e suportada',
  codes: 'a ferramenta usa um unico codigo por execucao, informado em answers.receipt',
};

export async function loadConfig(path) {
  const full = resolve(path);
  let raw;
  try {
    raw = await readFile(full, 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') {
      throw new Error(`config nao encontrada em ${full}. Copie config.example.json para config.json e edite.`);
    }
    throw err;
  }

  let config;
  try {
    config = JSON.parse(raw);
  } catch (err) {
    throw new Error(`config.json invalido: ${err.message}`);
  }

  validate(config, full);
  return config;
}

function validate(config, path) {
  const problems = [];

  for (const [key, why] of Object.entries(REJECTED)) {
    if (key in config || key in (config.answers || {}) || key in (config.browser || {})) {
      problems.push(`"${key}": ${why}`);
    }
  }

  if (!config.url || !/^https?:\/\//i.test(config.url)) {
    problems.push('"url" precisa ser um endereco http(s) valido');
  }

  const answers = config.answers || {};
  const policy = answers.scalePolicy;
  const policyOk =
    VALID_POLICIES.includes(policy) ||
    (typeof policy === 'object' && policy !== null && Number.isInteger(policy.index));
  if (!policyOk) {
    problems.push(
      `"answers.scalePolicy" precisa ser ${VALID_POLICIES.map((p) => `"${p}"`).join(', ')} ou { "index": N }. ` +
        'Ele nao tem valor padrao de proposito: a nota que voce da e uma escolha sua, nao da ferramenta.'
    );
  }

  const direction = answers.scaleDirection ?? 'auto';
  if (!VALID_DIRECTIONS.includes(direction)) {
    problems.push(`"answers.scaleDirection" precisa ser um de: ${VALID_DIRECTIONS.join(', ')}`);
  }

  for (const [i, rule] of (answers.overrides || []).entries()) {
    if (!rule || typeof rule !== 'object' || !rule.match) {
      problems.push(`"answers.overrides[${i}]" precisa ter a chave "match"`);
      continue;
    }
    if (rule.regex) {
      try {
        new RegExp(rule.match);
      } catch (err) {
        problems.push(`"answers.overrides[${i}].match" nao e uma regex valida: ${err.message}`);
      }
    }
  }

  if (problems.length) {
    throw new Error(`Problemas em ${path}:\n  - ${problems.join('\n  - ')}`);
  }
}

export { VALID_POLICIES, VALID_DIRECTIONS };
