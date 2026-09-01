/**
 * Portao de confirmacao humana.
 *
 * O envio final da pesquisa e irreversivel, entao ele nunca acontece sozinho:
 * o operador precisa revisar o resumo e digitar a confirmacao no terminal.
 * Nao existe flag para pular este passo.
 */

import readline from 'node:readline/promises';
import { stdin, stdout } from 'node:process';

const YES = new Set(['s', 'sim', 'y', 'yes', 'enviar']);

/**
 * Mostra o resumo do que sera enviado e espera a decisao do operador.
 * Retorna true apenas se a resposta for uma confirmacao explicita.
 */
export async function confirmSubmit(summary, { buttonLabel }) {
  if (!stdin.isTTY) {
    console.log('\n[!] Sem terminal interativo. O envio final exige confirmacao humana, entao nada foi enviado.');
    console.log('    Rode o comando num terminal de verdade para poder confirmar.');
    return false;
  }

  console.log('\n' + '='.repeat(64));
  console.log('REVISE ANTES DE ENVIAR');
  console.log('='.repeat(64));

  for (const page of summary) {
    console.log(`\n[pagina ${page.page}] ${page.heading || page.url}`);
    for (const item of page.filled) {
      console.log(`  - ${truncate(item.question, 68)}`);
      console.log(`      -> ${item.answer}`);
    }
    for (const item of page.skipped) {
      console.log(`  - ${truncate(item.question, 68)}`);
      console.log(`      -> (preenchido manualmente ou deixado em branco: ${item.reason})`);
    }
  }

  console.log('\n' + '-'.repeat(64));
  console.log(`Botao de envio detectado: "${buttonLabel}"`);
  console.log('Esta acao envia a pesquisa e nao pode ser desfeita.');
  console.log('-'.repeat(64));

  const rl = readline.createInterface({ input: stdin, output: stdout });
  try {
    const answer = await rl.question('\nConfirma o envio? [s/N] ');
    return YES.has(answer.trim().toLowerCase());
  } finally {
    rl.close();
  }
}

/** Pausa entre paginas quando o operador roda com --step. */
export async function confirmStep(label) {
  if (!stdin.isTTY) return true;
  const rl = readline.createInterface({ input: stdin, output: stdout });
  try {
    const answer = await rl.question(`\nAvancar clicando em "${label}"? [S/n] `);
    const t = answer.trim().toLowerCase();
    return t === '' || YES.has(t);
  } finally {
    rl.close();
  }
}

/** Espera o operador terminar de preencher a mao os campos pendentes. */
export async function waitForOperator(pending) {
  if (!stdin.isTTY) return;
  console.log(`\n[!] ${pending.length} campo(s) sem regra na config:`);
  for (const p of pending) {
    console.log(`      - ${truncate(p.question, 70)} (${p.reason})`);
  }
  const rl = readline.createInterface({ input: stdin, output: stdout });
  try {
    await rl.question('Preencha esses campos no navegador e pressione Enter para continuar... ');
  } finally {
    rl.close();
  }
}

function truncate(s, n) {
  const t = (s || '(sem enunciado)').replace(/\s+/g, ' ').trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}
