import {useState, useEffect} from 'react';

export function useAnonymousUser(): string {
    const [userId, setUserId] = useState<string>('');

    useEffect(() => {
        // Only runs on client side after mount
        const storedUserId = localStorage.getItem('openpharma_user_id');

        if (storedUserId) {
            console.log('Retrieved existing user ID', storedUserId);
            setUserId(storedUserId);
        } else {
            // Generate a new anonymous user ID
            const newUserId = `anon_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem('openpharma_user_id', newUserId);
            console.log('Generated new user ID', newUserId);
            setUserId(newUserId);
        }
    }, []);

    return userId;
}