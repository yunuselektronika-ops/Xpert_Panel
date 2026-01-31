import { createHashRouter } from "react-router-dom";
import { fetch } from "../service/http";
import { getAuthToken } from "../utils/authStorage";
import { Dashboard } from "./Dashboard";
import { XpertPanel } from "./XpertPanel";
import { Login } from "./Login";

const fetchAdminLoader = async () => {
    try {
        const token = getAuthToken();
        if (!token) {
            throw new Error("No token found");
        }
        
        const response = await fetch("/admin", {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        
        return response;
    } catch (error) {
        console.error("Admin loader failed:", error);
        throw error;
    }
};

export const router = createHashRouter([
    {
        path: "/",
        element: <Dashboard />,
        errorElement: <Login />,
        loader: fetchAdminLoader,
    },
    {
        path: "/xpert/",
        element: <XpertPanel />,
        errorElement: <Login />,
        loader: fetchAdminLoader,
    },
    {
        path: "/login/",
        element: <Login />,
    },
]);