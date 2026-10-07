export type AttributeRow = { id: number; name: string; value: string };

export function attributesFromRows(rows: AttributeRow[]): Record<string, string> {
  const values: Record<string, string> = {};
  for (const row of rows) {
    const name = row.name.trim();
    const value = row.value.trim();
    if (name) values[name] = value;
  }
  return values;
}
