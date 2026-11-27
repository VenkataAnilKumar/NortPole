/** Keep only the character ranges permitted in XML 1.0 text. */
export function xmlText(value: string): string {
  let result = "";
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    if (
      code === 9 || code === 10 || code === 13 ||
      (code >= 0x20 && code <= 0xd7ff) ||
      (code >= 0xe000 && code <= 0xfffd) ||
      code >= 0x10000
    ) {
      result += character;
    }
  }
  return result;
}
