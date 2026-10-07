import { AdminAccess } from "../../../components/admin-access";
import { ProductEditor } from "../../../components/product-editor";

export const dynamic = "force-dynamic";

export default function ProductEditorPage() {
  return (
    <AdminAccess>
      <ProductEditor />
    </AdminAccess>
  );
}
