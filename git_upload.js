const { execSync } = require('child_process');
const gitPath = 'C:/Program Files/Git/cmd/git.exe';

try {
    console.log('Initializing git...');
    execSync(`"${gitPath}" init`, { stdio: 'inherit' });
    
    console.log('Adding remote...');
    execSync(`"${gitPath}" remote add origin https://github.com/hedgemate2026/hedge.git`, { stdio: 'inherit' });
    
    console.log('Adding files...');
    execSync(`"${gitPath}" add .`, { stdio: 'inherit' });
    
    console.log('Creating commit...');
    execSync(`"${gitPath}" commit -m "Upload HedgeMate files"`, { stdio: 'inherit' });
    
    console.log('Pushing to jisheep...');
    execSync(`"${gitPath}" push -u origin jisheep`, { stdio: 'inherit' });
    
    console.log('Done!');
} catch (error) {
    console.error('Error during git operations:', error.message);
    process.exit(1);
}
