import { AdminAccess } from "../../../components/admin-access";
import { ProductCreateForm } from "../../../components/product-create-form";

export const dynamic = "force-dynamic";

export default function NewProductPage() {
  return <AdminAccess><ProductCreateForm /></AdminAccess>;
}
